from django import template
import django

from bacon.observers.tables import Table1D, TablePivot
from bacon.constants import MULTI_ARG_OPS

register = template.Library()


@register.simple_tag
def query_url(viewer, query):
	return viewer.get_url(query)


@register.simple_tag
def filter_url(table, lv):
	return table.filter_url(lv)


@register.simple_tag
def filter_url2(table, label_name, value):
	return table.filter_url2(label_name, value)


@register.simple_tag
def hide_value_url(table, label):
	return table.hide_value_url(label)


@register.simple_tag
def hide_labeled_value_url(table, label):
	return table.hide_labeled_value_url(label)


@register.simple_tag
def pivot_url(table, label):
	return table.pivot_url(label)


@register.simple_tag
def order_url(table, label, lvs=()):
	return table.order_url(label, lvs=lvs)


@register.simple_tag
def order_asc_url(table, label, lvs=()):
	return table.order_asc_url(label, lvs=lvs)


@register.simple_tag
def to_page_url(table, n):
	return table.table.to_string_page(n)


# HTML snippets available to the templates

@register.inclusion_tag('bacon/nav_panels.tmpl')
def nav_panels(panel):
	return {'panel': panel, 'MULTI_ARG_OPS': MULTI_ARG_OPS}


@register.simple_tag
def table(table):
	query = table.get_query()
	if query.pivot:
		tmpl = 'bacon/_table_pivot.tmpl'
		rtable = TablePivot(table)
	else:
		tmpl = 'bacon/_table_1d.tmpl'
		rtable = Table1D(table)

	tmpl = template.loader.get_template(tmpl)
	context = {'table': rtable}
	if django.VERSION[:2] < (1, 8):
		context = template.Context(context)
	return tmpl.render(context)


@register.inclusion_tag('bacon/_table_1d.tmpl')
def table_1d(table):
	return {'table': Table1D(table)}


@register.inclusion_tag('bacon/_table_pivot.tmpl')
def table_pivot(table):
	return {'table': TablePivot(table)}


@register.inclusion_tag('bacon/_table_pager.tmpl')
def pager(table):
	return {'table': table}


@register.inclusion_tag('bacon/_table_drop_axis_button.tmpl')
def drop_axis_button(table, label):
	return {'url': table.drop_axis_url(label)}


@register.inclusion_tag('bacon/_reset_order_button.tmpl')
def reset_order_button(table):
	return {'url': table.reset_order_url()}


@register.inclusion_tag('bacon/_order_buttons.tmpl')
def order_buttons(table, label, lvs=()):
	buttons = [
		[table.order_url(label, lvs), 'Order', u'\u2227'],
		[table.order_asc_url(label, lvs), 'Order ascending', u'\u2228'],
	]

	return {'buttons': buttons}


@register.inclusion_tag('bacon/_table_row_widgets.tmpl')
def table_row_widgets(table, title, row):
	widgets = table.table._widgets.get(title)
	return {'table': table, 'widgets': widgets, 'row': row}


@register.inclusion_tag('bacon/_table_row_widget.tmpl')
def table_row_widget(table, widget, row):
	nav = table.nav
	query = nav.row_filter(row.labels)
	url = widget.builder.to_string(query, widget.name)
	return {
		'label': widget.label,
		'url': url,
	}


@register.inclusion_tag('bacon/plot_tag.tmpl')
def plot_tag(plot):
	return {'plot': plot}


@register.tag
def debug(parser, token):
	try:
		tag, v = token.split_contents()
	except ValueError:
		raise template.TemplateSyntaxError(
			"%r takes a single value" % token.contents.split()[0])

	return DebugNode(v)


class DebugNode(template.Node):
	def __init__(self, v):
		self.v = template.Variable(v)

	def render(self, context):
		v = self.v.resolve(context)
		return repr(v)
