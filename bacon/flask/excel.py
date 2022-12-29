"""Render a xlwt workbook in Flask."""

import six
from flask import Response

import bacon.observers.excel


def render_excel(request, table, **kwargs):
    wb = bacon.observers.excel.render_excel(table, **kwargs)
    file = six.BytesIO()
    wb.save(file)
    return Response(file.getvalue(), content_type="aplication/vnd.ms-excel")
