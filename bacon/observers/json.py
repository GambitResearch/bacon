"""Export tables into json-serializable objects."""

import re
from itertools import count
from collections import OrderedDict

from bacon.utils.strings import ensure_unicode

import bacon.observers.nav
from bacon.observers.tables import Table1D, TablePivot


def render_nav_json(panel):
    axes = []
    filters = []
    values = []
    widgets = []

    olddim = -1
    for label, query in panel.nav.iter_expansions():
        if label.dimension != olddim:
            olddim = label.dimension
            dimension = OrderedDict(
                [
                    ("dimension", label.dimension or "Other axes"),
                    ("axes", []),
                ]
            )
            axes.append(dimension)
        axes[-1]["axes"].append(
            OrderedDict(
                [
                    ("label", ensure_unicode(label)),
                    ("url", panel.get_url(query) if query is not None else None),
                ]
            )
        )

    for f in panel.nav.iter_filters():
        filters.append(
            OrderedDict(
                [
                    (
                        "label",
                        f"{f.pretty_name} {f.pretty_op} {f.pretty_value}",
                    ),
                    ("drop_url", panel.get_url(f.query_without)),
                    ("invert_url", panel.get_url(f.query_invert)),
                    (
                        "related_urls",
                        OrderedDict(
                            [
                                (pretty_op, panel.get_url(query))
                                for pretty_op, query in f.query_related.items()
                            ]
                        ),
                    ),
                ]
            )
        )

    for label, query in panel.nav.hidden_values():
        values.append(
            OrderedDict(
                [
                    ("label", ensure_unicode(label)),
                    ("show_url", panel.get_url(query)),
                ]
            )
        )

    for w in panel.widgets:
        widgets.append(_render_widget(w, panel))

    rv = []
    if axes:
        rv.append(("axes", axes))
    if filters:
        rv.append(("filters", filters))
    if values:
        rv.append(("values", values))
    if widgets:
        rv.append(("widgets", widgets))

    return OrderedDict(rv)


def _render_widget(widget, panel):
    type_name = re.sub(
        r"([a-z])([A-Z])",
        lambda m: "%s_%s" % m.groups(),
        widget.__class__.__name__.replace("Widget", ""),
    ).lower()

    rv = OrderedDict(
        [
            ("type", type_name),
            ("label", widget.label),
        ]
    )

    if isinstance(widget, bacon.observers.nav.NavWidget):
        try:
            f = globals()["_render_" + widget.__class__.__name__]
        except KeyError:
            pass
        else:
            return f(rv, widget, panel)

    raise NotImplementedError(f"can't render {widget!r} in json")


def _render_ButtonsWidget(rv, widget, panel):
    rv["buttons"] = buttons = []
    for b in widget.buttons:
        buttons.append(
            OrderedDict(
                [
                    ("label", b.label),
                    ("image_url", b.image_url),
                    ("url", b.get_url(widget, panel)),
                ]
            )
        )

    return rv


def _render_DatesRangeWidget(rv, widget, panel):
    rv["urls"] = OrderedDict(
        zip(("no_value", "from_only", "to_only", "both_values"), widget.get_urls(panel))
    )

    f, t = panel.get_query().get_range(widget.axis)
    rv["values"] = {"from": str(f) if f else None, "to": str(t) if t else None}

    return rv


def render_table_json(table):
    rv = OrderedDict.fromkeys("pivots columns rows".split())
    links = LinkMap()

    if table.get_query().pivot:
        rtable = TablePivot(table)
        rv["pivots"], rv["columns"], rv["rows"] = _render_table_pivot(rtable, links)
    else:
        rtable = Table1D(table)
        rv["columns"], rv["rows"] = _render_table_1d(rtable, links)

    rv["pages"] = _render_pages(rtable, links)
    rv["links"] = links.get_map()

    return rv


def _render_table_1d(table, links):
    columns = []
    for t in table.label_titles():
        col = OrderedDict(
            [
                ("label", ensure_unicode(t)),
                ("type", "label"),
                ("links", dict(drop_axis=links.add(table.drop_axis_url(t)))),
            ]
        )
        columns.append(col)

        if t.allow_pivot:
            col["links"]["pivot"] = links.add(table.pivot_url(t))

    if columns:
        columns[0]["links"]["reset_order"] = links.add(table.reset_order_url())

    tcols = []
    for t in table.value_titles():
        col = OrderedDict(
            [
                ("label", ensure_unicode(t)),
                ("type", "value"),
                ("total", None),
                (
                    "links",
                    dict(
                        order=links.add(table.order_url(t)),
                        order_asc=links.add(table.order_asc_url(t)),
                        hide=links.add(table.hide_value_url(t)),
                    ),
                ),
            ]
        )
        columns.append(col)
        tcols.append(col)

    rows = []
    for row in table.rows():
        jrow = []
        rows.append(jrow)
        for label in row.labels:
            jrow.append(
                [
                    ensure_unicode(label),
                    {"filter": links.add(table.filter_url(label))},
                ]
            )
        for v in row.values:
            jrow.append(v.pretty)

    for col, tot in zip(tcols, table.totals()):
        col["total"] = tot.pretty

    return columns, rows


def _render_table_pivot(table, links):
    pivots = []
    for pivot_label, pivot_lvs in table.pivot_titles():
        pivots.append(
            OrderedDict(
                [
                    ("label", ensure_unicode(pivot_label)),
                    ("values", []),
                    (
                        "links",
                        dict(
                            pivot=links.add(table.pivot_url(pivot_label)),
                            drop_axis=links.add(table.drop_axis_url(pivot_label)),
                        ),
                    ),
                ]
            )
        )
        for label in pivot_lvs:
            pivots[-1]["values"].append(
                OrderedDict(
                    [
                        ("label", ensure_unicode(label)),
                        (
                            "links",
                            dict(
                                filter=links.add(table.filter_url(label)),
                                hide=links.add(table.hide_labeled_value_url(label)),
                            ),
                        ),
                    ]
                )
            )

    columns = []
    for t in table.label_titles():
        if t is None:
            continue
        columns.append(
            OrderedDict(
                [
                    ("label", ensure_unicode(t)),
                    ("type", "label"),
                    (
                        "links",
                        dict(
                            pivot=links.add(table.pivot_url(t)),
                            drop_axis=links.add(table.drop_axis_url(t)),
                        ),
                    ),
                ]
            )
        )

    if columns:
        columns[0]["links"]["reset_order"] = links.add(table.reset_order_url())

    tcols = []
    for pv, lvs in enumerate(table.pivot_lvs()):
        for t in table.value_titles():
            col = OrderedDict(
                [
                    ("label", ensure_unicode(t)),
                    ("pivot_value", pv),
                    ("type", "value"),
                    ("total", None),
                    (
                        "links",
                        dict(
                            order=links.add(table.order_url(t, lvs)),
                            order_asc=links.add(table.order_asc_url(t, lvs)),
                            hide=links.add(table.hide_value_url(t)),
                        ),
                    ),
                ]
            )
            columns.append(col)
            tcols.append(col)

    for t in table.value_titles():
        col = OrderedDict(
            [
                ("label", ensure_unicode(t)),
                ("type", "total"),
                ("total", None),
                (
                    "links",
                    dict(
                        order=links.add(table.order_url(t)),
                        order_asc=links.add(table.order_asc_url(t)),
                        hide=links.add(table.hide_value_url(t)),
                    ),
                ),
            ]
        )
        columns.append(col)
        tcols.append(col)

    for col, tot in zip(tcols, table.totals()):
        col["total"] = tot.pretty

    rows = []
    for row in table.rows():
        jrow = []
        rows.append(jrow)
        for label in row.labels:
            if label is None:
                continue
            jrow.append(
                [
                    ensure_unicode(label),
                    {"filter": links.add(table.filter_url(label))},
                ]
            )
        for v in row.values:
            jrow.append(v.pretty)
        for t in row.totals:
            jrow.append(t.pretty)

    return pivots, columns, rows


def _render_pages(table, link):
    rv = []
    for label, n, current in table.pages():
        url = table.table.to_string_page(n) if n is not None else None
        rv.append(
            OrderedDict(
                [
                    ("label", ensure_unicode(label)),
                    ("url", link.add(url)),
                ]
            )
        )
        if current:
            rv[-1]["current"] = True

    return rv


class LinkMap:
    def __init__(self):
        self.count = count()
        self.links = OrderedDict()

    def add(self, url):
        if url is None:
            return None
        try:
            rv = self.links[url]
        except KeyError:
            rv = self.links[url] = "L%d" % next(self.count)
        return rv

    def get_map(self):
        return OrderedDict((v, k) for k, v in self.links.items())
