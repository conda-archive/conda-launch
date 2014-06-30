Overview
========
`conda launch` provides a mechanism to turn a standard IPython Notebook into a web-accessible "app".  Inputs can
be provided either at the command line:

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

These are used to replace the contents of the first code cell in the notebook which is then executed and the resulting
notebook converted to HTML via `nbconvert` and passed back to the client.
 
Valid inputs and their type are specified via JSON meta-data that can either be put in a `conda.app` entry on the
notebook metadata cell, or just as a JSON string inside the last `raw_input` cell in the notebook.

Presently only simple input types are supported: `int`, `float`, `str`, `bool`.

Pre-requisites
==============

The following must be installed prior to using conda-launch:

* [conda](http://conda.pydata.org)
* [node](http://nodejs.com/)
* [pandoc](http://johnmacfarlane.net/pandoc/) (optional alternative to node)

Basic Usage
===========

This will start a local app server and open your browser to the specified app's input form:
```bash
$ conda launch notebook.ipynb
```

This will start a local app server and open your browser to the specified app using `GET` inputs of `foo=42` and
`bar=hello world` (appropriately URL-encoded):
```bash
$ conda launch notebook.ipynb  foo=42 bar="hello world"
```

Input Metadata
==============
At the end of your notebook, create a `raw_input` cell with JSON specifying the app interface and behavior. All keys
are optional.

Alternatively, the native Notebook meta-data facility may be used.  Add a key called `conda.app` and include the JSON
dictionary.

* `name`: a name for the notebook app
* `desc`: an application description that will be displayed as part of the input web form
* `inputs`: a dictionary with keys matching input parameters and values that are Python *callables* that
   can be used to convert a string into an instance of that type  
* `env`: a local environment name to use (takes prece
* `pkgs`: a list of package specifications that are required to run the app
* `channels`: a list of Conda channels that will be searched for package dependencies (in addition to the
    standard Conda package repositories)
* `output`: a string specifying the output mode (default: `html`)

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
 "env": "local-env-name",
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


TODO
====

* specify app by URL and GIST
* handle app's with associated resources/data in an archive file (zip or tarball)
* richer set of input types
* web form input validation
* support file inputs
* return results to terminal (all, and specific fields)
* allow a preamble that would setup/import type mapping functions/classes

FUTURE: Enhanced App Meta-Data
==============================
```
{
'envname' : 'name_of_app_environment' # optional, gives name of environment to create the default is 'appname'
'filesroot' : <relative path name of where files should be placed>  # full-path for where data files should go using $HOME and $PREFIX (default is $HOME/app_name_data)
'data' : {'name1': <base-64 encoded binary>, 'name2': <base-64 encoded binary>}
}
```