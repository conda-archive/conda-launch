#!/usr/bin/env python

# (c) 2012-2014 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# conda is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

import contextlib
import json
import logging
import os
import sys

from functools  import partial
from subprocess import PIPE
from Queue      import Empty

from jinja2     import Environment, PackageLoader

from IPython.nbconvert.exporters.html     import HTMLExporter
from IPython.nbconvert.exporters.markdown import MarkdownExporter
from IPython.nbconvert.exporters.python   import PythonExporter
from IPython.nbformat.current             import reads_json as nb_read_json
from runipy.notebook_runner               import NotebookRunner, NotebookError

import conda_api

from ipyapp.slugify import slugify
from ipyapp.config import MODE, FORMAT, TIMEOUT, FIXED_DEPS

log = logging.getLogger(__name__)

class NotebookAppFormatError(Exception):
    " App Notebooks need to be JSON and contain app meta-data"
    pass

class NotebookApp(object):
    """ Represents the state and operations to perform on an IPython Notebook that can be run as a
        standalone Notebook App.  Not to be confused with IPython.html.notebookapp.NotebookApp.
        Other than containing the JSON representation of the Notebook, this does not
        contain a reference to an IPython Notebook object.
    """
    def __init__(self, nbpath, nbargs_txt=None, timeout=None, mode=None, format=None, output=None, env=None):
        """ Representation of a particular instance of a Notebook App.  Can override the App-specific env (if any)

            :param nbpath:      path to notebook app file
            :param nbargs_txt:  notebook app arguments dictionary, all values as strings
            :param timeout:     maximum process runtime
            :param mode:        open [default], stream (to STDOUT), api (return result), quiet (write to disk)
            :param format:      html (default), {pdf, markdown -- #TODO}
            :param output:      specify a particular artifact to return from executed app #TODO
            :param env:         environment to use for notebook app invocation
        """
        self.nbdir      = os.path.dirname(nbpath)
        self.nbfile     = os.path.basename(nbpath)
        self.name       = self.nbfile.replace(".ipynb",'')

        self.json       = json.load(open(self.nbfile))
        self.parse_meta() # converts meta data in NB JSON into metadata dictionary on object
        self.desc       = self.meta.get('desc', self.name)
        self.inputs     = self.meta.get('inputs', {})

        # EXECUTION params
        self.nbargs     = {}
        if nbargs_txt:
            self.set_nbargs(**nbargs_txt)

        if timeout:
            self.timeout = timeout
        else:
            self.timeout = self.meta.get('timeout', TIMEOUT)

        if mode:
            self.mode       = mode
        else:
            self.mode = self.meta.get('mode', MODE)

        if format:
            self.format = format
        else:
            self.format = self.meta.get('format', FORMAT)

        if output:
            self.output = output
        else:
            self.output = self.meta.get('output', None)

        # ENVIRONMENT params

        # figure out the app environment name: API-specified, App meta-data, App name, or (if no deps), current env
        if env:                     # use the API-specified environment name (override)
            self.env    = env
        elif self.pkgs:             # if there are pkgs specified, figure out an env name
            self.env    = self.meta.get('env', slugify(self.name))
        else:                       # just use the current env
            self.env    = None

        self.pkgs       = self.meta.get('pkgs', [])
        self.channels   = self.meta.get('channels', [])


    def set_nbargs(self, **nbargs_txt):
        """ convert a dictionary of parameters and string representations of those parameters into
            their correct form using the 'inputs' type map
        """

        input_cell = {
             "cell_type":       "code",
             "collapsed":       False,
             "input":           [],
             "language":        "python",
             "metadata":        {},
             "outputs":         [],
             "prompt_number":   3
        }

        for var, type in self.inputs.items(): # iterate over all specified inputs
            try:
                value = nbargs_txt[var]
                input_cell['input'].append('{var} = {type}("{value}")\n'.format(var=var, type=type, value=value))
            except ValueError as ex:
                raise ValueError('Input param [%s, %s] not found in arguments [%s]' % (var, type, nbargs_txt))

        for input_cell_idx, cell in enumerate(self.json['worksheets'][0]['cells']):
            if cell['cell_type'] == 'code':
                # replace the first code cell with the input_cell
                break
        else:
            input_cell_idx = 0

        self.json['worksheets'][0]['cells'][input_cell_idx] = input_cell

    def fetch_meta(self):
        " find app meta data from notebook JSON "
        self.meta = {'inputs': {}}
        if 'conda.app' in self.json['metadata']:
            self.meta = self.json['metadata']['conda.app']
        else:
            # otherwise, look from the last cell backwards for the first "raw" cell,
            # and try to use its source as JSON meta
            for cell in reversed(self.json['worksheets'][0]['cells']):
                if cell['cell_type'] == 'raw':
                    try:
                        meta = json.loads("".join(cell['source']))
                    except ValueError:
                        pass # just use the default
                    break

    def set_meta(self):
        " set conda.app JSON metadata from current NotebookApp object "

        meta = dict(name=self.name,
                    desc=self.name,
                    inputs=self.inputs,
                    nbargs=self.nbargs,
                    timeout=self.timeout,
                    output=self.output,
                    mode=self.mode,
                    env=self.env,
                    channels=self.channels,
                    pkgs=self.pkgs,
                    )
        self.json['metadata']['conda.app'] = meta

    def startapp(self):
        "invoke the notebook app in a separate process with the appropriate environment"
        with cd(self.nbdir): # all execution now happens in the same directory as the notebook

            if self.env: # if there is a named env, try to create it and use it
                try:
                    conda_api.create(name=self.env, pkgs=FIXED_DEPS+self.pkgs)
                except conda_api.CondaEnvExistsError as ex:
                    pass # just use the existing environment
                env_dict=dict(name=self.env)
            else: # use the path to the current env
                env_dict=dict(path=conda_api.info()['default_prefix'])

            args = "--stream --mode {mode}".format(mode=self.mode).split()
            if self.output:
                args.extend("--output {output}".format(output=self.output).split())

            nbproc = conda_api.process(cmd="conda-launch", args=args, stdin=PIPE, stdout=PIPE, timeout=self.timeout,
                                        **env_dict)

            (out, err) = nbproc.communicate(input=self.json)

            if err:
                sys.stderr.write(err)

        return out


def run(nbjson, format=FORMAT):
    """ Run a notebook app 100% from JSON, return the result in the appropriate format

        :param nbjson: JSON representation of notebook app, ready to run
        :param format: html (default), {python, markdown #TODO}
    """
    try: # get the app name from metadata
        name  = nbjson['metadata']['conda.app']['name']
    except KeyError as ex:
        name  = "nbapp"

    # create a notebook object from the JSON
    nb_obj    = nb_read_json(nbjson)
    nb_runner = NotebookRunner(nb_obj)
    jinja_env = Environment(loader=PackageLoader('ipyapp', 'templates'))
    template = jinja_env.get_template('status.html')

    format = format.lower()
    if format=='html':
        Exporter = partial(HTMLExporter, template_file='output.html', resources=dict(nbapp=name))
    elif format=='md' or format=='markdown':
        Exporter = MarkdownExporter
    elif format=='py' or format=='python':
        Exporter = PythonExporter

    try:
        nb_runner.run_notebook(skip_exceptions=False)
        exporter  = Exporter()
        output, resources = exporter.from_notebook_node(nb_runner.nb)
        return output
    except Empty as ex:
        return template.render(message="ERROR: IPython Kernel timeout")
    except (NotImplementedError, NotebookError) as ex:
        return template.render(message="ERROR: Notebook contains unsupported feature: %s" % str(ex).split(':')[-1])
    except ImportError:
        return template.render(message="ERROR: nodejs or pandoc must be installed")

@contextlib.contextmanager
def cd(path):
    """A context manager which changes the working directory to the given
    path, and then changes it back to its previous value on exit.
    """
    prev_cwd = os.getcwd()
    if path:
        os.chdir(path)
    yield
    os.chdir(prev_cwd)