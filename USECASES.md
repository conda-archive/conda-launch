Eric is our end user.  Eric doesn't know any Python.  He wants to see Python in
his browser as much as he wants to see PHP in his browser.

Paula is our Pythonista.  Paula isn't a web developer, or even an app
developer, but she loves IPython Notebooks and creates ones that she would like
to be able to share as "graphical scripts" with her colleagues, like Eric.
Those colleagues want to run them but not have to look at or touch any code.

Simple app view of a notebook
-----------------------------

Eric: `conda launch "Power Series.ipynb"`

*end user:*

* Eric's default browser opens up with an input form asking for the parameters
  required to run the notebook `Power Series.ipynb`

* "Power Series.ipynb" is found in the current directory, and the abspath to
    this is passed to the nbapp server

* `conda launch` checks to see if the nbapp server is running, and if not,
    starts it.

* the notebook will be invoked in the directory where it is found, so any
    file operations are relative to that location (this may be on a remote server)

*developer:*

* Paula wrote `Power Series.ipynb`.  She needs to specify the interface spec:
    * this can be added as JSON to the notebook meta-data (either by hand or by
      a magic)
    * or to the last cell in the NB by marking it `raw` and using JSON

* The first cell in the notebook contains "model" or "example" inputs, so the
    notebook is fully runable as a regular notebook "out of the box" without
    any extra machinery.  When the notebook is run as an app, this cell will
    be replaced with the user-provided arguments.
