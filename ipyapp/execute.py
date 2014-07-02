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

from subprocess import PIPE
from Queue      import Empty

from IPython.nbformat.current             import reads_json as nb_read_json, new_text_cell, new_notebook, new_worksheet
from runipy.notebook_runner               import NotebookRunner, NotebookError

import conda_api
conda_api.set_root_prefix()

from ipyapp.slugify import slugify
from ipyapp.config import MODE, FORMAT, TIMEOUT, FIXED_DEPS, LOG_LEVEL

logging.basicConfig(level=LOG_LEVEL)
log = logging.getLogger(__name__)

class NotebookAppError(Exception):
    " General Notebook App error "
    pass

class NotebookAppExecutionError(NotebookAppError):
    " Notebook App error during execution "
    pass

class NotebookAppFormatError(NotebookAppError):
    " Notebook Apps need to be JSON and contain app meta-data"
    pass

class NotebookApp(object):
    """ Represents the state and operations to perform on an IPython Notebook that can be run as a
        standalone Notebook App.  Not to be confused with IPython.html.notebookapp.NotebookApp.
        Other than containing the JSON representation of the Notebook, this does not
        contain a reference to an IPython Notebook object.
    """
    def __init__(self, nbpath, nbargs_txt=None, timeout=None, mode=None, format=None, output=None, env=None,
                 template=None, override=False, **kwargs):
        """ Representation of a particular instance of a Notebook App.  Can override the App-specific env (if any)

            :param nbpath:      path to notebook app file
            :param nbargs_txt:  notebook app arguments dictionary, all values as strings
            :param timeout:     maximum process runtime
            :param mode:        open [default], stream (to STDOUT), api (return result), quiet (write to disk)
            :param format:      html (default), {pdf, markdown -- #TODO}
            :param output:      specify a particular artifact to return from executed app #TODO
            :param env:         environment to use for notebook app invocation
            :param override:    use these params (or defaults) in preference to app params, where possible
        """
        # NOTE: override is fragile. It relies on the defaults here matching the defaults from cli and server.

        self.nbdir      = os.path.dirname(nbpath)
        self.nbfile     = os.path.basename(nbpath)
        self.name       = self.nbfile.replace(".ipynb",'')

        self.json       = json.load(open(nbpath))
        self.fetch_meta() # converts meta data in NB JSON into metadata dictionary on object
        self.desc       = self.meta.get('desc', self.name)
        self.inputs     = self.meta.get('inputs', {})
        self.pkgs       = self.meta.get('pkgs', [])
        self.template   = template

        # EXECUTION params
        # TODO: remove the set_nbargs from init: leads to too many problems elsewhere. Do this in a subsequent step
        self.nbargs     = {}
        if nbargs_txt:
            log.debug('notebook app args (text format): %s' % nbargs_txt)
            self.set_nbargs(**nbargs_txt)

        if 'timeout' in self.meta:
            self.timeout = self.meta['timeout']
        elif timeout:
            self.timeout = timeout
        else:
            self.timeout = TIMEOUT

        if 'mode' in self.meta and not override:
            self.mode = self.meta['mode']
        elif mode:
            self.mode = mode
        else:
            self.mode = MODE

        if 'format' in self.meta and not override:
            self.format = self.meta['format']
        elif format:
            self.format = format
        else:
            self.format = FORMAT

        if 'output' in self.meta and not override:
            self.output = self.meta['output']
        elif output:
            self.output = output
        else:
            self.output = None

        # ENVIRONMENT params

        # figure out the app environment name: API-specified, App meta-data, App name, or (if no deps), current env

        if 'env' in self.meta and not override: # use the app-embedded env name
            self.env = self.meta['env']
        elif env:                               # use the API-specified environment name (override)
            self.env    = env
        elif self.pkgs:                         # if there are pkgs specified, figure out an env name
            self.env    = slugify(self.name)
        else:                                   # just use the current env
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
                input_cell['input'].append('{var} = {type}({value!r})\n'.format(var=var, type=type, value=value))
            except ValueError as ex:
                raise ValueError('Input param [%s, %s] not found in arguments [%s]' % (var, type, nbargs_txt))

        log.debug('notebook app arguments cell:\n%s' % "".join(input_cell['input']))

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
                        self.meta = json.loads("".join(cell['source']))
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

            cmd  = "conda"
            args = "launch --stream --mode {mode}".format(mode=self.mode).split()

            if self.output:
                args.extend("--output {output}".format(output=self.output).split())

            nbproc = conda_api.process(cmd=cmd, args=args, timeout=self.timeout,
                                       stdin=PIPE, stdout=PIPE, stderr=PIPE,
                                       **env_dict)

            self.set_meta() # write the current Notebook App meta-data to the JSON so it is available to the
                            # independent process that will run the notebook app
            (nbstream, err) = nbproc.communicate(input=json.dumps(self.json))

            # TODO: should probably reorganize so invocation updates this NotebookApp object with the executed notebook

            log.debug('notebook app execution output stream: %s' % nbstream)
            log.debug('notebook app execution error stream:  %s' % err)

            return (nbstream, err)

def run(nbtxt, output=None, view=False):
    """ Run a notebook app 100% from JSON (text stream), return the JSON (text stream)

        :param nbtxt: JSON representation of notebook app, ready to run
        :param view:   don't invoke notebook, just view in current form

        NOTE: `view` probably isn't useful, since the input will just be output again
    """

    # TODO: support output parameter to specify only returning certain attributes from notebook
    # create a notebook object from the JSON
    nb_obj    = nb_read_json(nbtxt)
    nb_runner = NotebookRunner(nb_obj)
    try: # get the app name from metadata
        name  = nb_obj['metadata']['conda.app']['name']
    except KeyError as ex:
        name  = "nbapp"

    try:
        if view:
            pass # then don't run it
        else:
            nb_runner.run_notebook(skip_exceptions=False)
        return nb_runner.nb

    except Empty as ex:
        sys.stderr.write("IPython Kernel timeout")
        err = mini_markdown_nb("""
Notebook Error
==============
ERROR: IPython Kernel timeout
```
{error}
```
""".format(error=str(ex).split(':')[-1]))
        return err
    except (NotImplementedError, NotebookError, ValueError) as ex:
        msg = str(ex).splitlines()[-1]
        sys.stderr.write(msg)
        err = mini_markdown_nb("""
Notebook Error
==============
Notebook contains unsupported feature or bad argument:
```
{error}
```
""".format(error=msg))
        return err
    except ImportError:
        msg = "nodejs or pandoc must be installed"
        sys.stderr.write(msg)
        err = mini_markdown_nb(msg)
        return err

def mini_markdown_nb(markdown):
    "create a single text cell notebook with markdown in it"
    nb   = new_notebook()
    wks  = new_worksheet()
    cell = new_text_cell('markdown', source=markdown)
    nb['worksheets'].append(wks)
    nb['worksheets'][0]['cells'].append(cell)
    return nb

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

