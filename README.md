Overview
========
`conda launch` provides a mechanism to turn a standard IPython Notebook into an
"app" with both command line and web-based interfaces.  The Notebooks remain
100% regular IPython Notebooks, so all other tools continue to work (IPython
Notebook server, `nbconvert`, etc.)

Inputs can be provided either at the command line:

```bash
s="some string of words" n=3
```

or via a RESTful interface:

```
http://server:port/appname?s=some string of words&n=3
```

or by an auto-generated web form:

```
http://server:port/appname
```

See the [Example
Apps](https://github.com/conda/conda-launch/tree/master/examples) for some
simple IPython Notebook examples of how this can be done in practice.

These inputs are passed into a copy of the Notebook as the *first code cell*,
with parameters cast to their appropriate type using an *input specification*
embedded in the notebook.  The notebook is then executed and the results
(output cells only) converted to HTML via `nbconvert` and opened in the browser
or passed back on the command line.
 
The *input specification* is done via JSON meta-data that can either be put in
a `conda.app` entry on the notebook metadata cell, inside the last `raw_input`
cell in the notebook.  Details of the format are below.

Presently only simple input types are fully supported: `int`, `float`, `str`,
`bool`.  Built-in container types (`dict`, `list`, `set`, `tuple`) work only
under limited circumstances.

Dependencies
============
The metadata can also include dependency specifications based on [Conda
packages](http://conda.pydata.org).  A sandbox environment will be created for
the app if necessary and re-used on subsequent app invocations.  This allows
packages that aren't in the Python Standard Library to be used.  The free
[Conda Package Repository](http://repo.continuum.io/pkgs/free/) contains most
popular Python packages that aren't in the PSL, however
[Binstar](http://binstar.org/) can be used for other custom user packages, and
the the app creator can add arbitrary *Binstar Channels* to the app metadata
specification -- these will be used to search for the dependencies for the app
sandbox environment that conda-launch will create.

Pre-requisites
==============

The following must be installed prior to using conda-launch:

* [conda](http://conda.pydata.org)
* [node](http://nodejs.com/)
* [pandoc](http://johnmacfarlane.net/pandoc/) (optional alternative to node)

Installation
============
```bash
conda install conda-launch
```

For the bleeding edge version, either get it from the [GitHub `conda-launch` repository](https://github.com/conda/conda-launch),
or install from the `ijstokes` Conda channel with `conda install -c ijstokes conda-launch`.

Although it is minimally tested, `conda-launch` can probably be run without `conda` or `conda_api` -- it should
gracefully skip any parts that require `conda_api` for sandbox environment creation or process invocation.  In this case,
it can be installed with the normal:

```bash
python setup.py install
```

and then invoked with `conda-launch` or `conda-appserver`.

Basic Usage
===========

This will invoke a notebook as an app, generate the output in a file
`notebook-output.html` and open it in the browser:

```bash
$ conda launch notebook.ipynb foo=42 bar="hello world"
```

This will start a local app server that lists all notebook files in this
directory and in the immediate sub-directories, allowing them to be run via a
persistent app server:

```bash
$ conda appserver start
```

Input Metadata
==============
At the end of your notebook, create a `raw_input` cell with JSON specifying the
app interface and behavior. All keys are optional.

Alternatively, the native Notebook meta-data facility may be used.  Add a key called `conda.app` and include the JSON
dictionary.

* `name`: a name for the notebook app
* `desc`: an application description that will be displayed as part of the input web form
* `inputs`: a dictionary with keys matching input parameters and values that are Python *callables* that
   can be used to convert a string into an instance of that type
* `timeout`: seconds to wait before app times out (default: `10`)
* `mode`: `open`: in browser, `quiet`: execute but do not display result, `stream`: output notebook JSON to `STDOUT` (default: `open`)
* `env`: a local environment name to use (takes precedence over `pkgs`)
* `pkgs`: a list of package specifications that are required to run the app
* `channels`: a list of Conda channels that will be searched for package dependencies
    (in addition to the standard Conda package repositorie)
* `output`: a string specifying the output mode (default: `html`) *[TODO]*

```python
{
 "name": "My Notebook App",
 "desc": "If `d`, multiply `a` and `b` then print `c`",
 "inputs": {
    "a": "int",
    "b": "float",
    "c": "str",
    "d": "bool"
    },
 "timeout": 10,
 "env": "existing-env-name",
 "pkgs": [
    "pkgspec1",
    "pkgspec2",
    "pkgspec3"
    ]
 "channels": [
    "http://conda.binstar.org/channel1",
    "http://conda.binstar.org/channel2"
    ],
 "output": "html|md|py|pdf|stream|quiet"
}
```

Command Line Options
====================
For current command line options, execute `conda launch -h` or `conda appserver -h`.

<b>`conda launch`</b>

```bash
usage: conda-launch [-h] [-v] [--stream] [-e ENV] [-m MODE] [-f FORMAT]
                    [-c CHANNEL] [-o OUTPUT] [--override] [-t TIMEOUT]
                    [--template TEMPLATE]
                    [notebook] ...

Invoke an IPython Notebook as an app and display the results

positional arguments:
  notebook              notebook app name, URL, or path
  nbargs                arguments to pass to notebook app

optional arguments:
  -h, --help            show this help message and exit
  -v, --view            view notebook app (do not execute or prompt for input)
  --stream              run notebook app from JSON on STDIN, return results on STDOUT
  -e ENV, --env ENV     conda environment to use (by name or path)
  -m MODE, --mode MODE  specify processing mode: [open|stream|quiet] (default: open) [TODO]
  -f FORMAT, --format FORMAT
                        result format: [html|md|py|pdf] (default: html) [TODO]
  -c CHANNEL, --channel CHANNEL
                        add a channel that will be used to look for the app [TODO]
  -o OUTPUT, --output OUTPUT
                        specify a single variable to return from processed notebook [TODO]
  --override            override values set in notebook app
  -t TIMEOUT, --timeout TIMEOUT
                        set a processing timeout (default: 10 sec)
  --template TEMPLATE   specify an alternative output template file

examples:
    conda launch MyNotebookApp.ipynb a=12 b="some string"
```

<b>`conda appserver`</b>

```bash
usage: conda-appserver [-h] [-p PORT] [--host HOST] action

Start a notebook app server

positional arguments:
  action                specify server action: daemon|start|stop|restart

optional arguments:
  -h, --help            show this help message and exit
  -p PORT, --port PORT  set the app server port
  --host HOST           set the app server ip

conda-appserver -p 5007
```

API and Configuration
=====================
All functionality is provided through the `ipyapp` Python package.  Configuration of behavior is a bit pants at the
moment: some configuration can be done via the command line, some can be done via the app *metadata*, and the rest
is done through the `ipyapp.config` module.  This is the order of precedence for items that can be set in more than
one place.

| `ipyapp.execute` | all the execution pieces around an `ipyapp.execute.NotebookApp` object |
| `ipyapp.cli`     | all the pieces for handling CLI invocation |
| `ipyapp.server`  | the basic Flask server |
| `ipyapp.fetch`   | the logic to find Notebook Apps and make them available to run |
| `ipyapp.config`  | configuration information |

All the other submodules are variations on code found elsewhere to support `ipyapp`

Notes
=====
* `matplotlib` inline graphics will require the notebook to have a line (early on) with the magic:
```
%matplotlib inline
```

Questions, Problems, Suggestions, Issues
========================================
Questions and discussion should probably go on the [Conda mailing list](https://groups.google.com/a/continuum.io/forum/#!forum/conda),
while any bugs or enhancement suggestions should go into the [GitHub issue tracker](https://github.com/conda/conda-launch/issues).

Please provide enough information so we can help reproduce your problem/bug:

* platform
* version (ideally `conda info` and `conda list | grep conda`)
* exactly what you invoked at the command line
* the full stack trace or error message that you get

TODO
====

* specify app by URL and GIST
* handle app's with associated resources/data in an archive file (zip or tarball)
* richer set of input types
* web form input validation
* support file inputs
* return results to terminal (all, and specific fields) -- `output` option/spec
* allow a preamble that would setup/import type mapping functions/classes
* embed data in the notebook file (using *base64* encoding) that will be
  reified to filesystem on app invocation 
* improve configuration