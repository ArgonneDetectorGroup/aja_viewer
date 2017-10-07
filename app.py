from __future__ import division

import flask
from io import BytesIO

import aja_tools as aja

app = flask.Flask(__name__)

#Try to load from local user config file
#If that doesn't exist, use the default
try:
    app.config.from_pyfile('config.py')
except IOError:
    app.config.from_pyfile('config_default.py')

#Locatio of database
LOG_PATHS = app.config['LOG_PATHS']

#Set the debug level
app.debug = app.config['DEBUG']

@app.route('/')
def index():
    global LOGS
    LOGS = []
    machine_names = LOG_PATHS.keys()

    return flask.render_template('index.html', machine_names = machine_names)

@app.route('/display_jobs', methods=['GET', 'POST'])
def display_jobs():
    machine_name = flask.request.form['machine_name']
    jobs = aja.build_jobs_dict(LOG_PATHS[machine_name])
    global LOGS
    LOGS = aja.build_logs_list(LOG_PATHS[machine_name], jobs)

    return flask.render_template('display_jobs.html', logs = LOGS, machine_name=machine_name)

@app.route('/static_plot', methods=['GET', 'POST'])
def gen_static_plot():
    machine_name = flask.request.args['machine_name']
    index = int(flask.request.args['index'])
    global LOGS

    fig = aja.plot_log(LOGS[index]['path'], machine_name, show_layers=True)

    output = BytesIO()

    fig.savefig(output)
    output.seek(0)
    return flask.send_file(output, mimetype='image/png')

@app.route('/show_plot', methods=['GET', 'POST'])
def show_plot():
    machine_name = flask.request.form['machine_name']
    #Why does jinja do 1-indexing?????
    index = int(flask.request.form['submit_plt'])
    global LOGS
    job = LOGS[index]['job']
    recipe_list = LOGS[index]['recipe']

    return flask.render_template('show_plots.html',
                                    recipes = recipe_list,
                                    job=job,
                                    index=index,
                                    machine_name=machine_name)
