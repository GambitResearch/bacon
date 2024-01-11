"""Render a csv file in Flask."""
from io import StringIO

from flask import Response

import bacon.observers.csv


def render_csv(request, table, **kwargs):
    with StringIO() as csvfile:
        bacon.observers.csv.render_csv(csvfile, table, **kwargs)
        return Response(csvfile.getvalue(), content_type="text/csv")
