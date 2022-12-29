"""Render a json result in Django."""

from __future__ import absolute_import

from django.http import HttpResponse
from django.conf import settings

import json
import bacon.observers.json


def render_table_json(request, table):
    data = bacon.observers.json.render_table_json(table)
    return render_json(request, data)


def render_nav_json(request, panel):
    data = bacon.observers.json.render_nav_json(panel)
    return render_json(request, data)


def render_json(request, data):
    if settings.DEBUG:
        jkws = {"indent": 2, "separators": (",", ": ")}
    else:
        jkws = {"separators": (",", ":")}

    response = HttpResponse(content_type="application/json")
    json.dump(data, response, **jkws)
    return response
