import json 
from StringIO import StringIO

from IPython.config import Config
from IPython.nbconvert.exporters.html import HTMLExporter
from IPython.nbformat.current import read as nb_read, write

from flask import Flask, request

from werkzeug.exceptions import BadRequestKeyError

from runipy.notebook_runner import NotebookRunner, NotebookError

app = Flask(__name__, template_folder='templates')

@app.route("/ipyapp/custom.css")
def custom_css():
    return ""

@app.route("/ipyapp/<nbname>")
def nblaunch(nbname):
    input_cell = json.loads("""
    { 
     "cell_type": "code",
     "collapsed": false,
     "input": [],
     "language": "python",
     "metadata": {},
     "outputs": [],
     "prompt_number": 3
    }
""")

    nb = json.load(open(nbname + ".ipynb"))
    # TODO: nb['worksheets'][0]['cells'][-1]['cell_type'] == 'raw' etc. etc.
    app_meta = json.loads("".join(nb['worksheets'][0]['cells'][-1]['source']))
    for var, t in app_meta['inputs'].iteritems():
        try:
            value = eval("repr({cast}('{expr}'))".format(cast=t, expr=request.args[var]))
        except BadRequestKeyError as ex:
            value = eval("repr({cast}())".format(cast=t))
        input_cell['input'].append('{var} = {value}\n'.format(var=var, value=value))
        
    nb['worksheets'][0]['cells'][0] = input_cell

    nb_obj = nb_read(StringIO(json.dumps(nb)), 'json')
    nb_runner = NotebookRunner(nb_obj)
    nb_runner.run_notebook(skip_exceptions=False)

    exporter = CustomHTMLExporter(config=Config({'HTMLExporter':{'default_template': 'noinputs.tpl'}}))
    output, resources = exporter.from_notebook_node(nb_runner.nb)
    return output

from IPython.nbconvert.preprocessors.base import Preprocessor

class AppifyNotebook(Preprocessor):
    def preprocess_cell(self, cell, resources, cell_index):
        if cell.cell_type == 'raw':
            cell.source = ''
        if hasattr(cell, "prompt_number"):
            del cell.dict()['prompt_number']
        if hasattr(cell, "input"):
            del cell.dict()['input']
        return cell, resources

class CustomHTMLExporter(HTMLExporter):

    def __init__(self, **kw):
        super(CustomHTMLExporter, self).__init__(**kw)
        self.register_preprocessor(AppifyNotebook, enabled=True)

if __name__ == "__main__":
    app.run(debug=True)

