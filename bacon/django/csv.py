"""Render a csv file in Django."""

from django.http import HttpResponse

import bacon.observers.csv


def render_csv(request, table, **kwargs):
	response = HttpResponse(content_type='text/csv')
	bacon.observers.csv.render_csv(response, table, **kwargs)
	return response
