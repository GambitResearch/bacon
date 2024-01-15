"""Render a xlwt workbook in Flask."""
from io import BytesIO

from flask import Response

import bacon.observers.excel


def render_excel(request, table, **kwargs):
    wbook = bacon.observers.excel.render_excel(table, **kwargs)
    with BytesIO() as xlsfile:
        wbook.save(xlsfile)
        return Response(xlsfile.getvalue(), content_type="aplication/vnd.ms-excel")
