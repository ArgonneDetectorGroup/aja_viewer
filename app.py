from __future__ import division

import os
import sqlite3
import flask
import numpy as np
import pandas as pd
import plotly as ply
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import matplotlib.figure
from matplotlib.figure import Figure
from io import BytesIO

app = flask.Flask(__name__)

#Try to load from local user config file
#If that doesn't exist, use the default
try:
    app.config.from_pyfile('config.py')
except IOError:
    app.config.from_pyfile('config_default.py')

#Locatio of database
DATABASE = app.config['DATABASE']

#Set the debug level
app.debug = app.config['DEBUG']

#Allow a custom path prefix for deploying into a subdirectory
#while using CGI on a server that won't let you edit the Apache
#configuration files
PATH_PREFIX = app.config['PREFIX']

#Make a wrapper that always passes the path_prefix to the templates
#so it makes calls a little cleaner
def render_template_prefix(template, **kwargs):
    return flask.render_template(template, path_prefix=PATH_PREFIX, **kwargs)

def get_db():
    db = getattr(flask.g, '_database', None)
    if db is None:
        db = flask.g._database = sqlite3.connect(DATABASE)
    return db

def gen_timeseries(db, table_name, recipe):
    query = """select * from {} where
            Recipe_Steps like ?""".format(table_name)

    df = pd.read_sql_query(query, db, params=(recipe,), index_col='Date_Time', parse_dates=['Date_Time'])

    df = df[df.columns[(df != 0).any()]]

    keys_to_plot = df.select_dtypes(['number']).drop(['Layer_#', 'Wafer_#_Loaded'], axis=1).columns.tolist()

    num_cols = 3
    num_rows = np.ceil((len(keys_to_plot)+1)/num_cols)

    axes = []

    fig = Figure(figsize=(9, 9))
    canvas = FigureCanvas(fig)

    for ix, key in enumerate(keys_to_plot):
        ax = fig.add_subplot(num_rows, num_cols, ix+1)
        ax.set_title(key)
        axes.append(ax)

    for key, val in df.groupby(('Layer_#', 'Logfile_Path')):
        #print(val.index[0])
        filtered_val = val.select_dtypes(['number']).drop(['Layer_#', 'Wafer_#_Loaded'], axis=1)

        for ix, key in enumerate(keys_to_plot):

            yvals = filtered_val[key].values
            xvals = (filtered_val.index-filtered_val.index[0]).total_seconds()
            axes[ix].plot(xvals, yvals, label=str(filtered_val.index[0]))

    fig.canvas.draw()
    for ax in axes:
        ax.set_xticklabels(labels=ax.get_xmajorticklabels(), rotation=45)
        ax.set_xlabel('Time (s)')

    fig.tight_layout()

    return fig

@app.route('/')
def index():
    df = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table'", get_db())
    table_names = df['name'].values.tolist()
    return render_template_prefix('index.html', table_names = table_names)

@app.route('/static_plot', methods=['GET', 'POST'])
def gen_static_plot():
    table_name = flask.request.args['table_name']
    recipe = flask.request.args['recipe']

    fig = gen_timeseries(get_db(), table_name, recipe)

    output = BytesIO()
    # canvas.print_png(output)
    # response=flask.make_response(output.getvalue())
    # response.headers['Content-Type'] = 'image/png'

    fig.savefig(output)
    output.seek(0)
    return flask.send_file(output, mimetype='image/png')

    return response

@app.route('/recipe_plots', methods=['GET', 'POST'])
def show_plot():
    table_name = flask.request.form['table_name']
    recipe = flask.request.form['submit_plt']
    interactive = flask.request.form['interactive']

    if interactive == 'True':

        fig = gen_timeseries(get_db(), table_name, recipe)

        #Wrap in fancy interactive plotly div
        output = ply.offline.plot_mpl(fig, output_type='div', show_link="False",include_plotlyjs="False")

        return render_template_prefix('show_plots.html',
                                    interactive=True,
                                    recipe_name = recipe,
                                    table_name=table_name,
                                    plot_output=flask.Markup(output))

    else:
        return render_template_prefix('show_plots.html',
                                    interactive=False,
                                    recipe_name = recipe,
                                    table_name=table_name)

@app.route('/recipe_frequency', methods=['GET', 'POST'])
def calc_recipe_frequency():
    table_name = flask.request.form['table_name']

    if table_name == 'AJA_Dielectrics':

        query = """select Recipe_Steps, count(Recipe_Steps) as count from
               (select distinct Recipe_Steps, Job_Name, "Layer_#"
               from AJA_Dielectrics
               where ("RF#1_Shutter" like "OPEN"
               OR "RF#4A_Shutter" like "OPEN"
               OR "RF#4B_Shutter" like "OPEN"
               OR "RF#4C_Shutter" like "OPEN"
               OR "DC#1_Shutter" like "OPEN"
               OR "DC#5C_Shutter" like "OPEN")
               AND Recipe_Steps not like "%TURNOFF%") as internalquery
               group by Recipe_Steps
               order by count desc
               """
    elif table_name == 'AJA_Metals':

        query = """select Recipe_Steps, count(Recipe_Steps) as count from
               (select distinct Recipe_Steps, Job_Name, "Layer_#"
               from AJA_Metals
               where ("RF#1_Shutter" like "OPEN"
               OR "RF#2_Shutter" like "OPEN"
               OR "DC#1_Shutter" like "OPEN"
               OR "DC#5A_Shutter" like "OPEN"
               OR "DC#5B_Shutter" like "OPEN"
               OR "DC#5C_Shutter" like "OPEN"
               OR "DC#5D_Shutter" like "OPEN")
               AND Recipe_Steps not like "%OFF") as internalquery
               group by Recipe_Steps
               order by count desc
               """
    else:
        raise Exception("Unknown Table")

    df = pd.read_sql_query(query, get_db())

    df_head = df.columns.tolist()
    df_data = df.values.tolist()

    return render_template_prefix('recipe_freqs.html',
                                 df_head = df_head,
                                 df_data = df_data,
                                 table_name = table_name)


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(flask.g, '_database', None)
    if db is not None:
        db.close()
