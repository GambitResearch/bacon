"""Render a xlwt workbook in Django."""

from django.http import HttpResponse

import bacon.observers.excel


def render_excel(request, table, **kwargs):
	wb = bacon.observers.excel.render_excel(table, **kwargs)
	response = HttpResponse(content_type='application/vnd.ms-excel')
	wb.save(response)
	return response
