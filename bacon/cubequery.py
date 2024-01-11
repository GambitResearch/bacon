"""CubeQuery: a query definition over a `CubeDef`."""

from operator import itemgetter

_op_antonym_pairs = [
    ("eq", "ne"),
    ("gt", "le"),
    ("lt", "ge"),
    ("in", "ni"),
    ("hasall", "hasnotall"),
    ("hasnone", "hasany"),
    ("subsetof", "notsubsetof"),
    ("supersetof", "notsupersetof"),
    ("disjointfrom", "intersects"),
    ("equals", "notequals"),
    ("match", "nmatch"),
]

_op_antonym = {op: antonym for op, antonym in _op_antonym_pairs}
_op_antonym.update({antonym: op for op, antonym in _op_antonym_pairs})
_op_antonym["hasonly"] = "notequals"

_op_sets = [
    set(["eq", "ne", "gt", "lt", "ge", "le"]),
    set(["in", "ni"]),
    set(
        [
            "hasall",
            "hasnotall",
            "hasnone",
            "hasany",
            "subsetof",
            "notsubsetof",
            "supersetof",
            "notsupersetof",
            "disjointfrom",
            "intersects",
            "equals",
            "notequals",
        ]
    ),
    set(["match", "nomatch"]),
]


def invert_op(op):
    return _op_antonym[op]


def related_ops(op):
    for op_set in _op_sets:
        if op in op_set:
            return op_set
    return set()


class CubeQuery(object):
    def __init__(self):
        self._axes = []
        self._values = []
        self._filters = []
        self._hidden_values = []
        self._order = []
        self._pivots = set()

    def __repr__(self):
        return f"<{self.__class__.__name__} dim={self.dim} at 0x{id(self):08X}>"

    def copy(self):
        """Return a deep copy of the query."""
        rv = self.__class__()
        rv._axes = self._axes[:]
        rv._values = self._values[:]
        rv._filters = self._filters[:]
        rv._order = self._order[:]
        rv._hidden_values = self._hidden_values[:]
        rv._pivots = set(self._pivots)
        return rv

    @property
    def dim(self):
        return len(self._axes)

    @property
    def axes(self):
        return self._axes[:]

    @property
    def values(self):
        return [
            name
            for (name, visible) in self._values
            if (visible and name not in self._hidden_values)
        ]

    @property
    def all_values(self):
        return list(map(itemgetter(0), self._values))

    @property
    def hidden_values(self):
        return self._hidden_values[:]

    @property
    def filters(self):
        return self._filters[:]

    @property
    def order(self):
        return self._order[:]

    def has_axis(self, axis):
        if axis in self._axes:
            return True
        else:
            for f in self._filters:
                if f[0] == axis:
                    return True

        return False

    @property
    def pivot(self):
        return [a for a in self._axes if a in self._pivots]

    def add_axis(self, name, before=None, after=None):
        """Return a new `CubeQuery` with an added dimension."""
        rv = self.copy()
        if before is None and after is None:
            pos = len(rv._axes) - len(self._pivots)
        elif after is not None:
            pos = rv._axes.index(after) + 1
        else:
            pos = rv._axes.index(before)

        rv._axes.insert(pos, name)
        return rv

    def remove_axis(self, name):
        """Return a new `CubeQuery` with a removed dimension."""
        rv = self.copy()
        rv._axes.remove(name)
        if name in rv._pivots:
            rv._pivots.remove(name)
            for i, o in enumerate(rv._order):
                if o[2]:
                    rv._order[i] = (o[0], o[1], [])

        return rv

    def add_value(self, name, visible=True):
        """Return a new `CubeQuery` with an added output value."""
        rv = self.remove_value(name)
        rv._values.append((name, visible))
        return rv

    def remove_value(self, name):
        rv = self.copy()
        for i, (n, v) in enumerate(rv._values):
            if n == name:
                del rv._values[i]
                break

        return rv

    def add_filter(self, name, value, operator="eq"):
        """Return a new `CubeQuery` with an added filter."""
        rv = self.copy()
        f = (name, operator, value)
        if f not in rv._filters:
            rv._filters.append(f)
        return rv

    def remove_filter(self, name, value=None, operator=None):
        """Return a new `CubeQuery` with filters removed."""
        rv = self.copy()
        if operator is None:
            rv._filters = [f for f in rv._filters if f[0] != name]
        else:
            rv._filters = [f for f in rv._filters if f != (name, operator, value)]
        return rv

    def swap_filter(self, name, value, operator, new_operator):
        """Return a new `CubeQuery` with filter operator changed."""
        rv = self.copy()
        original = (name, operator, value)
        replacement = (name, new_operator, value)
        rv._filters = [replacement if f == original else f for f in rv._filters]
        return rv

    def invert_filter(self, name, value, operator):
        """Return a new `CubeQuery` with filter inverted."""
        return self.swap_filter(name, value, operator, invert_op(operator))

    def related_filters(self, name, value, operator):
        """Return a dictionary of new `CubeQuery`s with other ops in place of this filter."""
        return {
            other_op: self.swap_filter(name, value, operator, other_op)
            for other_op in related_ops(operator)
        }

    def get_range(self, axis):
        """Return start and end values of the range of an axis."""
        value_from = value_to = None
        for name, op, value in self._filters:
            if name == axis:
                if op == "ge":
                    value_from = value
                elif op == "le":
                    value_to = value
                elif op == "eq":
                    value_from = value_to = value
                    break  # that settles...

        return value_from, value_to

    def get_filter(self, axis, wanted_op="eq"):
        """Return the value of a filter if any with operator `wanted_op`"""
        for name, op, value in self._filters:
            if name == axis and op == wanted_op:
                return value
        else:
            return None

    def uses_axis(self, label):
        """
        Return true if a label is used (either as axis or in filtering)

        Used to judge if a query must be further refined (e.g. if the query
        uses the ccy_code we can show currency-specific measures
        """
        if label in self._axes:
            return True
        else:
            for f in self._filters:
                if f[0] == label and f[1] == "eq":
                    return True

        return False

    def hide_value(self, name):
        rv = self.copy()
        if name not in rv._hidden_values:
            rv._hidden_values.append(name)
        return rv

    def show_value(self, name):
        rv = self.copy()
        if name in rv._hidden_values:
            rv._hidden_values.remove(name)
        return rv

    def set_pivot(self, name):
        rv = self.copy()
        if name in rv._axes:
            rv._axes.remove(name)
        rv._axes.append(name)
        rv._pivots.add(name)

        # If orderding was on some pivoted table now it is unreliable
        for i, o in enumerate(rv._order):
            if o[2]:
                rv._order[i] = (o[0], o[1], [])

        return rv

    def unset_pivot(self, name):
        rv = self.copy()
        rv._pivots.discard(name)

        # If orderding was on some pivoted table now it is unreliable
        for i, o in enumerate(rv._order):
            if o[2]:
                rv._order[i] = (o[0], o[1], [])

        return rv

    def order_by(self, name, values=()):
        """Set the order for the query.

        `name` should be a value name. It can be prefixed by ``-``
        to specify a reverse order is required.

        ``values`` should be a sequence with as many elements as the pivot
        axes: if specified sort by that pivoted column instead of the totals.

        TODO: add ordering by labels (currently it can be simulated specifying
                the order labels appear in the query).
        """
        rv = self.copy()
        if name.startswith("-"):
            rv._order = [("-", name[1:], values)]
        else:
            rv._order = [("+", name, values)]

        return rv

    def no_order(self):
        """Reset the natural order for the query."""
        rv = self.copy()
        del rv._order[:]
        return rv
