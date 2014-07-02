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

Notes
=====
* `matplotlib` inline graphics will require the notebook to have a line (early on) with the magic `%matplotlib inline`

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
