"""Render a csv file in Flask."""
import six
from flask import Response

import bacon.observers.csv


def render_csv(request, table, **kwargs):
	file = six.StringIO()
	bacon.observers.csv.render_csv(file, table, **kwargs)
	return Response(file.getvalue(), content_type='text/csv')
