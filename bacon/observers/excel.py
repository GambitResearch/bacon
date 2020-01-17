"""Export tables into Excel worksheets."""

import datetime
from bacon.utils.strings import ensure_unicode

from ._wswrapper import WSWrapper
import xlwt

from bacon.observers.tables import Table1D, TablePivot


def render_excel(table, title='Sheet'):
	wb = xlwt.Workbook(encoding="utf-8")
	ws = WSWrapper(wb.add_sheet(title))

	if table.get_query().pivot:
		rtable = TablePivot(table)
		render_table_pivot(ws, rtable)
	else:
		rtable = Table1D(table)
		render_table_1d(ws, rtable)

	ws.newline()
	ws.write(u"Report generated on %s" %
		datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
		# font height in 1/20th of points of course...
		style=xlwt.easyxf('font: height 160'))
	ws.newline()

	return wb

# TODO: numeric formats should be configurable by the cubedef.
style_label = xlwt.easyxf()
style_label_date = xlwt.easyxf(num_format_str='DD/MM/YY')
style_value = xlwt.easyxf(num_format_str='#,##0.00')
style_title = xlwt.easyxf('font: bold on; align: horiz center')
style_total = xlwt.easyxf('font: bold on', num_format_str='#,##0.00')


def render_table_1d(ws, table):
	for t in table.label_titles():
		ws.write(ensure_unicode(t), style=style_title)
	for t in table.value_titles():
		ws.write(ensure_unicode(t), style=style_title)
	ws.newline()
	ws.freeze_titles()

	for slice, labels, values in table.rows():
		for label in labels:
			write_label(ws, label)
		for v in values:
			ws.write(v.value, style=style_value)
		ws.newline()

	totals = table.totals()
	if totals is not None:
		for t in table.label_titles():
			ws.write(None, style=style_total)
		for v in table.totals():
			ws.write(v.value, style=style_total)
		ws.newline()

	ws.autofit()


def render_table_pivot(ws, table):
	# Pivot values lines
	for i, (pivot_label, pivot_lvs) in enumerate(table.pivot_titles()):
		ws.write_merge(len(table.label_titles()),
			ensure_unicode(pivot_label), style=style_title)
		for label in pivot_lvs:
			ws.write_merge(len(table.value_titles()),
				ensure_unicode(label), style=style_title)
		if i == 0:
			ws.write_merge(len(table.value_titles()), u"Total",
				rowspan=len(table.pivot_labels), style=style_title)
		ws.newline()

	# Column titles line
	for t in table.label_titles():
		ws.write(t and ensure_unicode(t) or None, style=style_title)
	for label in table.pivot_lvs():
		for t in table.value_titles():
			ws.write(ensure_unicode(t), style=style_title)
	for t in table.value_titles():
		ws.write(ensure_unicode(t), style=style_title)
	ws.newline()
	ws.freeze_titles()

	# Table data
	for slice, labels, values, totals in table.rows():
		for label in labels:
			write_label(ws, label)
		for v in values:
			ws.write(v.value, style=style_value)
		for t in totals:
			ws.write(t.value, style=style_total)
		ws.newline()

	# Totals row
	totals = table.totals()
	if totals is not None:
		for t in table.label_titles():
			ws.write(None, style=style_total)
		for v in table.totals():
			ws.write(v.value, style=style_total)
		ws.newline()

	ws.autofit()

styles_label = {
	datetime.date: style_label_date,
	# default: style_label
}


def write_label(ws, label):
	if label:
		content = label.excel
	else:
		content = None
	style = styles_label.get(type(content), style_label)
	ws.write(content, style=style)
