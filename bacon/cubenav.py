#!/usr/bin/env python
from operator import attrgetter

try:
    from itertools import imap

    text_type = unicode
except ImportError:
    text_type = str

from bacon.cubequery import CubeQuery
from collections import namedtuple
from bacon.constants import MULTI_ARG_OPS


CurrentFilter = namedtuple(
    "CurrentFilter",
    """
	name pretty_name
	op pretty_op
	value pretty_value str_value
	query_without query_invert query_related""".split(),
)


class Navigator:
    """Allows interactive navigation around a dataset."""

    def __init__(self, name, builder, cubedef):
        self.name = name
        self.builder = builder
        builder.cubedef = self._cubedef = cubedef
        self.query = None

    def parse_query(self, query):
        """Parse the query representation *string* updating *query*.

        The query is checked for consistence against the `querydef`: if anything
        goes wrong raise `QueryError` or such.

        If everything was fine, set the `query` attribute to the updated query.
        """
        self.query = self.builder.parse(self.name, query)

    def to_string(self, query=None):
        if query is None:
            query = self.query

        return self.builder.to_string(query, name=self.name)

    def get_label(self, name):
        return self._cubedef.get_label(name)

    def get_measure(self, name):
        return self._cubedef.get_measure(name)

    def iter_expansions(self):
        query = self.query

        labels = self._cubedef.get_labels()
        labels.sort(key=lambda l: (l.dimension or "\uffff", l.rank))

        for label in labels:
            if not label.hidden:
                yield label, self._expand_if_you_can(query, label)

    def _expand_if_you_can(self, query, label):
        """Return a query with an added dimension if it can be added, else None."""
        name = label.name

        # labels used by the query
        used_labels = set(map(self._cubedef.get_label, query.axes))

        # If we already used it, no way
        if label in used_labels:
            return None

        dim_labels = set(self._cubedef.get_connected(name))

        # If we haven't used the dimension at all, it's ok to have it
        if not used_labels & dim_labels:
            return query.add_axis(name)

        # if we did, we must limit the used axes to a completely ordered set
        anc = set(self._cubedef.get_ancestors(name))
        des = set(self._cubedef.get_descendants(name))
        if not (anc | des) >= (dim_labels & used_labels):
            return None

        # The set would be ok: add the label so that the order is maintained
        des &= used_labels
        if des:
            ref = min(des, key=attrgetter("rank")).name
            return query.add_axis(name, before=ref)

        anc &= used_labels
        if anc:
            ref = max(anc, key=attrgetter("rank")).name
            return query.add_axis(name, after=ref)

        # Not sure if this line ever gets triggered
        return query.add_axis(name)

    def iter_filters(self):
        filters = self.query.filters
        if self.query.filters:
            return self._iter_filters(filters)
        else:
            return ()

    def _iter_filters(self, filters):
        query = self.query

        for name, op, value in filters:
            label = self._cubedef.get_label(name)
            # idea: this puts back an axis when the filter is removed,
            # which is the reverse of hiding the axis when filtering on
            # one of its value. But it can lead to an explosive number of
            # rows, e.g. when filtering on the event, then remove some
            # larger limit such as a week, then removing the event filter.
            # TODO: enable it after adding some paging support.
            # query = self._expand_if_you_can(query, label) or query
            if op not in MULTI_ARG_OPS:
                pretty_value = label.pretty(value, None)
            else:
                pretty_value = ", ".join(label.pretty(v, None) for v in sorted(value))
            yield CurrentFilter(
                name=name,
                op=op,
                value=value,
                str_value=text_type(value),
                pretty_name=text_type(label),
                pretty_op=self._pretty_op.get(op, op),
                pretty_value=pretty_value,
                query_without=query.remove_filter(name, value, op),
                query_invert=query.invert_filter(name, value, op),
                query_related={
                    self._pretty_op.get(other_op, other_op): new_filter
                    for other_op, new_filter in query.related_filters(
                        name, value, op
                    ).items()
                },
            )

    _pretty_op = {
        "eq": "=",
        "ne": "is not",
        "gt": ">",
        "ge": "\u2265",
        "lt": "<",
        "le": "\u2264",
        "in": "is any of:",
        "ni": "is none of:",
        "hasall": "has all of:",
        "hasnone": "has none of:",
        "hasany": "has any of:",
        "hasonly": "has only:",
    }

    def hidden_values(self):
        return list(self._hidden_values())

    def _hidden_values(self):
        query = self.query
        for m in self._cubedef.get_measures():
            if not getattr(m, "show_by_default", True) and m.name not in query.values:
                yield m, query.add_value(m.name)

        for name in query.hidden_values:
            yield self._cubedef.get_measure(name), query.show_value(name)

    def filter(self, lv):
        query = self.query
        name = lv.label.name
        query = query.add_filter(name, lv.value, lv.filter_op)
        try:
            query = query.remove_axis(name)
        except:
            # we are currently not able to remove the axis we are filtering on if it
            # was added by Controller.finish_query()
            pass
        return query

    def row_filter(self, lvs):
        query = CubeQuery()
        for lv in lvs:
            name = lv.label.name
            query = query.add_filter(name, lv.value, lv.filter_op)

        for name, operator, value in self.query.filters:
            query = query.add_filter(name, value, operator=operator)

        return query

    def drop_axis(self, label):
        query = self.query
        query = query.remove_axis(label.name)
        return query

    def hide_value(self, label):
        query = self.query
        if getattr(label, "show_by_default", True):
            query = query.hide_value(label.name)
        else:
            query = query.remove_value(label.name)

        order = query.order
        if order:
            odir, olabel, ovals = order[0]
            if olabel == label:
                query = query.no_order()

        return query

    def hide_labeled_value(self, lv):
        query = self.query
        for label, op, value in query.filters:
            if label == lv.label and op == "ni":
                query = query.remove_filter(label, value=value, operator=op)
                value = value.union((lv.value,))
                query = query.add_filter(label, value, operator=op)
                break
        else:
            query = query.add_filter(lv.label.name, (lv.value,), operator="ni")

        return query

    def order_by(self, label, values):
        return self.query.no_order().order_by(label.name, values)

    def order_by_asc(self, label, values):
        return self.query.no_order().order_by("-" + label.name, values)

    def reset_order(self):
        return self.query.no_order()

    @property
    def axes(self):
        return list(map(self._cubedef.get_label, self.query.axes))

    @property
    def pivot(self):
        return list(map(self._cubedef.get_label, self.query.pivot))

    def set_pivot(self, label):
        query = self.query

        if not label.allow_pivot:
            # just ignore the request instead of returning a query that will bomb
            return query

        query = query.set_pivot(label.name)
        return query

    def unset_pivot(self, label):
        query = self.query
        query = query.unset_pivot(label.name)
        return query

    def remove_dimension_filters(self, axis_name):
        """Return the query with all the filters in a dimension removed.

        *axis_name* is the name of one of the labels in the dimension to clear.
        """
        query = self.query

        label = self.get_label(axis_name)
        dimension = label.dimension
        if not dimension:
            return query

        for name, op, value in query.filters:
            label = self.get_label(name)
            if label.dimension == dimension:
                query = query.remove_filter(name, value, op)

        return query


class UrlMaker:
    """
    Helper mixin to make urls from something that has get_url and a navigator.
    """

    def filter_url(self, lv):
        query = self.nav.filter(lv)
        return self.get_url(query)

    def filter_url2(self, label_name, value):
        query = self.nav.query
        query = query.add_filter(label_name, value)
        return self.get_url(query)

    def drop_axis_url(self, label):
        try:
            query = self.nav.drop_axis(label)
        except ValueError:
            # this happens when attempting to remove an axis added by
            # Controller.fininsh_query(). For the moment we treat these axis as
            # not removable
            return None
        else:
            return self.get_url(query)

    def hide_value_url(self, label):
        query = self.nav.hide_value(label)
        return self.get_url(query)

    def hide_labeled_value_url(self, label):
        query = self.nav.hide_labeled_value(label)
        return self.get_url(query)

    def pivot_url(self, label):
        if label not in self.nav.pivot:
            query = self.nav.set_pivot(label)
        else:
            query = self.nav.unset_pivot(label)

        return self.get_url(query)

    def order_url(self, label, lvs=()):
        order = self.nav.query.order
        if order:
            odir, olabel, ovals = order[0]
            if odir != "-" and olabel == label:
                if (not lvs and not ovals) or list(ovals) == [lv.value for lv in lvs]:
                    return None

        values = [lv.value for lv in lvs]
        query = self.nav.order_by(label, values)
        return self.get_url(query)

    def order_asc_url(self, label, lvs=()):
        order = self.nav.query.order
        if order:
            odir, olabel, ovals = order[0]
            if odir == "-" and olabel == label:
                if (not lvs and not ovals) or list(ovals) == [lv.value for lv in lvs]:
                    return None

        values = [lv.value for lv in lvs]
        query = self.nav.order_by_asc(label, values)
        return self.get_url(query)

    def reset_order_url(self):
        if self.query.order:
            return self.get_url(self.nav.reset_order())
