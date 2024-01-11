"""Render a json result in Flask."""
import json
import flask
import bacon.observers.json


def render_table_json(request, table):
    data = bacon.observers.json.render_table_json(table)
    return render_json(request, data)


def render_nav_json(request, panel):
    data = bacon.observers.json.render_nav_json(panel)
    return render_json(request, data)


def render_json(request, data):
    if flask.current_app.debug:
        jkws = {"indent": 2, "separators": (",", ": ")}
    else:
        jkws = {"separators": (",", ":")}

    response = flask.Response(json.dumps(data, **jkws), content_type="application/json")
    return response
