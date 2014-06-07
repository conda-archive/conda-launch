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
At the end of your notebook, create a `raw_input` cell with JSON specifying the input names and types.  The type must
be a Python *callable* that can be used to convert a string into an instance of that type.  The `desc` key is optional
and can be used to provide an application description that will be displayed as part of the input web form.

```python
{"inputs": {
    "a": "int",
    "b": "float",
    "c": "str",
    "d": "bool"
    },
 "desc": "If `d`, multiply `a` and `b` then print `c`"
}
```

TODO
====

* specify app by URL and GIST
* handle app's with associated resources/data in an archive file (zip or tarball)
* conda environments for app dependencies
* richer set of input types
* web form input validation
* support file inputs
* return results to terminal (all, and specific fields)

FUTURE: Enhanced App Meta-Data
==============================
```
{
'depends': [list of requirement specification strings],  # default ipython-notebook
'platform-depends': {<platform> : [list of specs], <platform2> : [list of specs]}, # optional
'appname' : default is name of notebook  # optional
'envname' : 'name_of_app_environment' # optional, gives name of environment to create the default is 'appname'
'filesroot' : <relative path name of where files should be placed>  # full-path for where data files should go using $HOME and $PREFIX (default is $HOME/app_name_data)
'data' : {'name1': <base-64 encoded binary>, 'name2': <base-64 encoded binary>}
}
```