"""CubeDef: an object that can describe how to navigate a dataset."""
from __future__ import annotations

import pytz
import re
from calendar import day_name, month_name
from datetime import date, datetime, timedelta
from operator import attrgetter

import networkx as nx

from bacon import errors
from bacon import accumulators as accs
from bacon.graphs import ancestors, descendants
from bacon.utils.strings import ensure_unicode
from bacon.utils.dateutils import date_to_quarter


class DataDef:
    """Definition of a dataset.

    The datadef is similar to a table schema in a relational database: it
    describes the fields available on a dataset.
    """

    def __init__(self):
        self._fields = []
        self._fields_by_name = {}

    def add_field(self, field):
        self._fields.append(field)
        self._fields_by_name[field.name] = field

    def get_field(self, name):
        return self._fields_by_name[name]

    __getitem__ = get_field

    def get_fields(self):
        return self._fields

    def wrap_rows(self, dataset):
        for raw_object in dataset:
            yield Row(self, raw_object)


class Row:
    """
    A simple wrapper that makes a row of data act like a dictionary,
    based on the DataDef fields.
    """

    def __init__(self, datadef, raw):
        self.raw = raw
        self.datadef = datadef

    def __getitem__(self, field_name):
        return self.datadef[field_name].extract(self.raw)


class CubeDef:
    """Definition of a dataset and the different ways to read it.

    The cubedef extends the definition of the data beyond what you get
    in a relational database, with definitions of how to accumulate
    values and how they relate to each other.
    """

    def __init__(self):
        self._labels = {}
        self._measures = {}
        self._graph = nx.DiGraph()

    def add_label(self, label: Label) -> Label:
        """Add a new label definition."""
        if not isinstance(label, Label):
            raise TypeError(f"expected 'Label' instance, {label!r} got instead")

        name = label.name
        self._labels[name] = label
        self._graph.add_node(name)

        if label.child_of:
            if isinstance(label.child_of, str):
                self.add_hierarchy(label.child_of, name)
            else:
                for parent in label.child_of:
                    self.add_hierarchy(parent, name)

        if label.parent_of:
            if isinstance(label.parent_of, str):
                self.add_hierarchy(name, label.parent_of)
            else:
                for child in label.parent_of:
                    self.add_hierarchy(name, child)

        return label

    def get_label(self, name):
        """Return a label by name.

        Raise `DataError` if the name is not known.
        """
        try:
            return self._labels[name]
        except KeyError:
            raise errors.DataError(f"label not defined: '{name}'")

    def get_labels(self):
        """Return the list of all the labels defined."""
        return list(self._labels.values())

    def add_measure(self, measure):
        """Add a new measure definition."""
        if not isinstance(measure, Label):
            raise TypeError(f"expected 'Label' instance, {measure!r} got instead")

        self._measures[measure.name] = measure

    def get_measure(self, name):
        """Return a measure by name.

        Raise `DataError` if the name is not known.
        """
        try:
            return self._measures[name]
        except KeyError:
            try:
                return self._labels[name]
            except KeyError:
                raise errors.DataError(f"measure not defined: '{name}'")

    def get_measures(self):
        """Return the list of all the measures defined."""
        return list(self._measures.values())

    def add_hierarchy(self, name_from, name_to):
        """Add a new hierarchy arc between two labels.

        Hierarchies transform the set of labels in a disconnected DAG.
        every connected subset of the graph is a "dimension".
        """
        # for checking
        l1 = self.get_label(name_from)
        l2 = self.get_label(name_to)

        self._graph.add_edge(name_from, name_to)

        # Boost the rank of descendants to add some ordering to the hierarchy
        l1.rank = l2.rank = max(l1.rank, l2.rank)
        for l in self.get_descendants(name_from):
            l.rank += 1

        # maintain the dimensions
        if l1.dimension is None and l2.dimension is None:
            pass  # no dimension
        elif l1.dimension is None or l2.dimension is None:
            # extend the dimension
            dim = l1.dimension or l2.dimension
            for l in self.get_connected(name_from):
                l.dimension = dim
        elif l1.dimension == l2.dimension:
            pass
        else:
            raise errors.DataError(
                "dimensions conflict between %s (on label %s) "
                "and %s (on label %s)" % (l1.dimension, l1, l2.dimension, l2)
            )

    def cls(self, record):
        return ""

    def get_connected(self, name):
        """Return the list of labels connected to *name*."""
        for names in nx.connected_components(self._graph.to_undirected()):
            if name in names:
                return list(map(self.get_label, names))

    def get_ancestors(self, name):
        """Return the list of labels ancestors of *name* in its dimension."""
        return list(map(self.get_label, ancestors(self._graph, name)))

    def get_descendants(self, name):
        """Return the list of labels descendants of *name* in its dimension."""
        return list(map(self.get_label, descendants(self._graph, name)))


class Field:
    """
    A basic field that can extract and render data from a record.  If
    you want to filter on it, use the Label class instead.
    """

    def __init__(self, name, extract=None, title=None, pretty=None):
        self._name = name
        if extract is not None:
            self.extract = extract
        self.title = ensure_unicode(title or name.replace("_", " ").title())
        if pretty is not None:
            self.pretty = pretty

    @property
    def name(self):
        return self._name

    def __repr__(self):
        return f"<{type(self).__name__} {self._name!r} at 0x{id(self):08X}>"

    def __unicode__(self):
        return self.title

    def __str__(self):
        return self.title

    def __eq__(self, other):
        if not isinstance(other, str):
            other = other.name
        return self._name == other

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash(self._name)

    def extract(self, record):
        # default to attrgetter
        return getattr(record, self.name)

    def pretty(self, value, record=None):
        if isinstance(value, str):
            return ensure_unicode(value)
        return ensure_unicode(value)


class Label:
    """Definition of a label on the records in a dataset.

    The label can be either subclassed or populated by init arguments.
    """

    def __init__(
        self,
        name_or_field,
        extract=None,
        acc=None,
        title=None,
        pretty=None,
        parse=None,
        unparse=None,
        key=None,
        reverse=False,
        sql_expression=None,
        django_expression=None,
        django_fields=None,
        django_select_related=[],
        django_prefetch_related=[],
        child_of=None,
        parent_of=None,
        dimension=None,
        cls="label",
        allow_pivot=True,
        hidden=False,
    ):
        if isinstance(name_or_field, Field):
            self.field = name_or_field
            if extract:
                self.extract = lambda record: extract(self.field.extract(record))
            if title:
                self._title = title
        else:
            self.field = Field(
                name=name_or_field, extract=extract, title=title, pretty=pretty
            )

        if parse is not None:
            self.parse = parse
        if unparse is not None:
            self.unparse = unparse

        self.acc = acc or accs.Group
        if key is not None:
            self.key = key
        self.reverse = reverse

        self.child_of = child_of
        self.parent_of = parent_of
        self.dimension = dimension

        self.cls = isinstance(cls, str) and (lambda v, record: cls) or cls
        self.allow_pivot = allow_pivot
        self.hidden = hidden
        self._sql_expression = sql_expression or self.field.name
        self.django_expression = django_expression
        self.django_fields = django_fields
        self.django_select_related = django_select_related
        self.django_prefetch_related = django_prefetch_related

        self.rank = 0

    def key(self, value):
        # Generic key function for nullable types which puts nulls first.
        if value is None:
            return ()
        else:
            return (value,)

    def get_filter_op(self):
        return "eq"

    @property
    def name(self):
        return self.field.name

    @property
    def title(self):
        return getattr(self, "_title", None) or self.field.title

    def __unicode__(self):
        return ensure_unicode(self.title)

    def __str__(self):
        return str(self.title)

    def __hash__(self):
        return hash(self.field)

    def extract(self, record):
        return self.field.extract(record)

    def pretty(self, value, record=None):
        return self.field.pretty(value, record)

    def __repr__(self):
        return f"<{type(self).__name__} {self.name!r} at 0x{id(self):08X}>"

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return self.field == other.field
        elif isinstance(other, str):
            return self.field == other
        else:
            return None

    def parse(self, s):
        return s

    def unparse(self, v):
        if isinstance(v, str):
            return ensure_unicode(v)
        return ensure_unicode(v)

    def to_excel(self, value, record=None):
        return self.pretty(value, record=record)

    @property
    def sql_expression(self):
        return self._sql_expression

    def add_sql_sources(self, sql):
        return sql

    def add_sql_label(self, sql):
        return sql.add_group(self.name, self.sql_expression)

    def add_sql_measure(self, sql):
        return self.add_sql_label(sql)

    sql_opmap = {
        "ge": ">=",
        "gt": ">",
        "le": "<=",
        "lt": "<",
        "eq": "=",
        "ne": "<>",
        "in": "in",
        "ni": "not in",
        "match": "~",
        "nmatch": "!~",
    }

    django_opmap = {
        "ge": "__gte",
        "gt": "__gt",
        "le": "__lte",
        "lt": "__lt",
        "eq": "",
        "ne": "",
        "in": "__in",
        "ni": "__in",
        "match": "__regex",
        "nmatch": "__regex",
        "contains": "__contains",
        "icontains": "__icontains",
    }

    django_exclude = ["nmatch", "ni", "ne"]

    def add_q_filter(self, queryset, op, value):
        """
        Filter the queryset by self.django_expression.

        If django_expression is a string we apply a filter or exclude depending on the 'op'.

        e.g. django_expression = "username", op = "ne" and value = "bob"
        will exclude all usernames equal to bob from the queryset.

        If django expression is a Q object we filter or exclude depending on whether the value
        is True or False.

        e.g. django_expression=Q(capitalist__name="John Doe") & Q(system_object="xyz")
        and value is True will filter the queryset to match the django_expression.
        """

        if type(self.django_expression) == str:
            if op not in self.django_opmap:
                raise NotImplementedError(
                    f"The operation {op} is not implemented as a django query filter"
                )
            qop = self.django_opmap[op]

            # handle "field:in:" or "field:ni:" which would result in
            # "field in ()" below.
            if value == frozenset((None,)):
                if op == "in":
                    qop = ""
                elif op == "ni":
                    qop = ""
                value = None

            kwargs = {self.django_expression + qop: value}
            if op in self.django_exclude:
                queryset = queryset.exclude(**kwargs)
            else:
                queryset = queryset.filter(**kwargs)
        else:
            # django_expression is Q object which we apply in boolean fashion according to value
            if value == "True":
                queryset = queryset.filter(self.django_expression)
            else:
                queryset = queryset.exclude(self.django_expression)
        return queryset

    def add_sql_filter(self, sql, op, value):
        qop = self.sql_opmap[op]
        if value is None:
            if op == "eq":
                qop = "is"
            elif op == "ne":
                qop = "is not"

        # handle "field:in:" or "field:ni:" which would result in
        # "field in ()" below.
        elif value == frozenset((None,)):
            if op == "in":
                qop = "is"
            elif op == "ni":
                qop = "is not"
            value = None

        # note: adding parens around the value placeholder below create errors
        # when the value is a tuple (as in where blah in ((1,2)): that's
        # a sql syntax error)
        filter = "((%s) %s %%s)" % (self.sql_expression, qop)

        # Comparisons with null, e.g. `(null = value)`, returns null (falsy)
        # in sql, so make sure to check for None/null separately
        if isinstance(value, frozenset):
            if None in value:
                value = value - set([None])
                if op == "in":
                    filter = f"((({self.sql_expression}) is null) or {filter})"

            else:
                if op == "ni":
                    filter = f"((({self.sql_expression}) is null) or {filter})"

            value = tuple(value)
        else:
            if value is not None and op == "ne":
                filter = f"((({self.sql_expression}) is null) or {filter})"

        sql = sql.add_filter(filter, value)

        return sql


def pretty_from_format(fmt):
    def pretty(v, record=None):
        return fmt % v if v is not None else ""

    return pretty


class NullableLabel(Label):
    """A label that can handle None values outside the data type space."""

    def __init__(self, name, none_value="", none_label="(none)", **kwargs):
        super().__init__(name, **kwargs)
        self.none_value = none_value
        self.none_label = none_label

    def pretty(self, value, record=None):
        if value is not None:
            return super().pretty(value, record)
        else:
            return self.none_label

    def parse(self, s):
        if s != self.none_value:
            return super().parse(s)
        else:
            return None

    def unparse(self, v):
        if v is not None:
            return super().unparse(v)
        else:
            return self.none_value


class AttributeLabel(NullableLabel):
    """A label extracting an attribute from the record."""

    def __init__(self, name, attr=None, extract=None, **kwargs):
        if attr is None:
            attr = name
        if extract is None:
            extract = attrgetter(attr)
        self.attr = attr
        if "sql_expression" not in kwargs:
            kwargs["sql_expression"] = attr
        super().__init__(name, extract=extract, **kwargs)


class SetLabel(NullableLabel):
    """A set-valued label, based on Postgres text[] columns

    N.B. you can use GIN indexes on these
    """

    def key(self, d):
        return d or frozenset()

    def get_filter_op(self):
        return "hasonly"

    def pretty(self, value, record=None):
        if isinstance(value, str):
            return value
        elif value is None or value == ((None,)):
            return self.none_label
        else:
            return "{%s}" % ",".join(sorted(value))

    def add_q_filter(self, queryset, op, value):
        """Django query operations based on PostgreSQL ArrayField

        https://docs.djangoproject.com/ja/1.9/ref/contrib/postgres/fields/
        """
        if op in ("hasonly", "equals"):
            kwargs = {self.django_expression: list(value)}
            queryset = queryset.filter(**kwargs)
        elif op in ("hasany", "intersects"):
            kwargs = {self.django_expression + "__overlap": list(value)}
            queryset = queryset.filter(**kwargs)
        elif op in ("hasall", "supersetof"):
            kwargs = {self.django_expression + "__contains": list(value)}
            queryset = queryset.filter(**kwargs)
        elif op in ("hasnone", "disjointfrom"):
            kwargs = {self.django_expression + "__overlap": list(value)}
            queryset = queryset.exclude(**kwargs)
        elif op == "subsetof":
            kwargs = {self.django_expression + "__contained_by": list(value)}
            queryset = queryset.filter(**kwargs)
        else:
            raise NotImplementedError
        return queryset

    def add_sql_filter(self, sql, op, value):
        if value == frozenset((None,)) or value is None:
            value = "{}"
        else:
            value = "{%s}" % ",".join(value)
        sql_filter, values = self.get_filter(op, value)
        sql = sql.add_filter(sql_filter, *values)
        return sql

    def get_filter(self, op, value):
        if op in ("hasany", "intersects"):
            return "((%s) && %%s)" % self.field.name, [value]
        elif op in ("hasall", "supersetof"):
            return "((%s) @> %%s)" % self.field.name, [value]
        elif op in ("hasonly", "equals"):  # or op == 'eq':
            if value == "{}":
                return f"(({self.field.name}) is null)", []
            else:
                return "(((%s) @> (%%s)) and ((%s) <@ (%%s)))" % (
                    self.field.name,
                    self.field.name,
                ), [value, value]
        elif op in ("hasnone", "disjointfrom"):
            return "(not (%s) && %%s)" % self.field.name, [value]
        elif op == ("subsetof"):
            return "((%s) <@ %%s)" % self.field.name, [value]
        elif op.startswith("not"):
            try:
                base_filter, values = self.get_filter(op[3:], value)
                return "(not " + base_filter + ")", values
            except ValueError:
                # We prefer to raise our own error
                pass
        raise ValueError(f"Unexpected op {op} for SetLabel {self.field.name}")


class SetLabelAny(SetLabel):
    """Set-valued label based on Postgres text[] columns
    Overridden default operation to hasany for a more inclusive behaviour
    """

    def get_filter_op(self):
        return "hasany"


class IntTypeLabel(Label):
    def parse(self, s):
        # TODO, enforce, check, etc, raise a better error, etc
        try:
            return int(s)
        except ValueError as ex:
            raise errors.DataError(str(ex))


class BoolTypeLabel(Label):
    def __init__(
        self, *args, label_true="Yes", label_false="No", label_null="Unknown", **kwargs
    ):
        self.label_true = label_true
        self.label_false = label_false
        self.label_null = label_null
        super().__init__(*args, **kwargs)

    _q_to_b = {"0": False, "1": True, "": None}

    def parse(self, s):
        # TODO, enforce, check, etc, raise a better error, etc
        return self._q_to_b[s]

    _b_to_q = {False: "0", True: "1", None: ""}

    def unparse(self, v):
        return self._b_to_q[v]

    def pretty(self, value, record=None):
        if value is True:
            return self.label_true
        if value is False:
            return self.label_false
        if value is None:
            return self.label_null
        raise ValueError(value)


class DatetimeDateTypeLabel(Label):
    DATETIME_FORMAT = "%Y-%m-%d"

    def parse(self, s):
        try:
            return datetime.strptime(s, self.DATETIME_FORMAT)
        except ValueError:
            raise errors.DataError(f"bad date: {s!r}")

    def unparse(self, v):
        return v.strftime(self.DATETIME_FORMAT) if v else None


class DatetimeTypeLabel(DatetimeDateTypeLabel):
    DATETIME_FORMAT = "%Y-%m-%dT%H:%M"

    def parse(self, s):
        datetime_obj = super().parse(s)
        if (
            datetime_obj.tzinfo is None
            or datetime_obj.tzinfo.utcoffset(datetime_obj) is None
        ):
            return pytz.utc.localize(datetime_obj)
        return datetime_obj


class DateTypeLabel(DatetimeDateTypeLabel):
    def parse(self, s):
        return super().parse(s).date()


class DatetimeDateHierarchyLabelMixin(DatetimeDateTypeLabel):
    SUFFIX = None
    DEFAULT_TITLE = None

    def __init__(self, name_or_field, **kwargs):
        self._title = kwargs.get("title", self.DEFAULT_TITLE)
        super().__init__(name_or_field, **kwargs)

    def __unicode__(self):
        return self.title

    @property
    def name(self):
        return f"{self.field.name}{self.SUFFIX}"

    def _convert_datetime_if_required(self, rv):
        return rv

    def extract(self, record):
        try:
            rv = self.field.extract(record)
        except AttributeError:
            # this is an sql dataset: there is no "date" attribute
            # but there is an already aggregated date
            # TODO: ugly as butt, catching the error is fragile,
            # refactor somehow.
            return getattr(record, self.name)
        else:
            if rv is not None:
                rv = self._convert_datetime_if_required(rv)
                return self.classify(rv)

    def classify(self, date):
        # Subclass in the hierarchy class to build the equivalence classes
        # from Python objects (if the dataset comes from sql, it's already
        # partitioned)
        return date


class DateHierarchyLabel(DateTypeLabel, DatetimeDateHierarchyLabelMixin):
    def key(self, d):
        return d or date.fromtimestamp(0)

    def _convert_datetime_if_required(self, rv):
        return rv.date() if isinstance(rv, datetime) else rv


class DatetimeHierarchyLabel(DatetimeTypeLabel, DatetimeDateHierarchyLabelMixin):
    def key(self, d):
        return d or datetime.fromtimestamp(0)


_re_delta = re.compile(r"-?\d+$")


class DatetimeDateTruncLabelMixin(DatetimeDateHierarchyLabelMixin):
    def add_sql_filter(self, sql, op, value):
        sql = super().add_sql_filter(sql, op, value)

        if op in ("ge", "gt", "eq") and not isinstance(self, DayLabel):
            # Leave out Daylabel because it doesn't truncate.
            # d >= date_trunc('foo', d) so if we're selecting
            # WHERE date_trunc('foo', d) >= value, we can add
            # WHERE d >= value which postgres can optimise
            qop = ">="
            filter = "((%s) %s %%s)" % (self._sql_expression, qop)
            sql = sql.add_filter(filter, value)

        return sql


class DateTruncLabel(DateHierarchyLabel, DatetimeDateTruncLabelMixin):
    @property
    def sql_expression(self):
        return f"date_trunc('{self.SQL_DATE_FIELD}', {self._sql_expression})::date"


class DatetimeTruncLabel(DatetimeHierarchyLabel, DatetimeDateTruncLabelMixin):
    @property
    def sql_expression(self):
        return f"date_trunc('{self.SQL_DATE_FIELD}', {self._sql_expression})"


class DatetimePartLabel(DatetimeDateHierarchyLabelMixin):
    """
    A 1-based field obtained by extracting some integer from a date.

    Values are prepended with PREFIX when displayed.
    """

    PREFIX = NotImplemented
    MAX_VALUE = NotImplemented
    SQL_DATE_FIELD = NotImplemented

    def classify(self, date):
        raise NotImplementedError()

    def pretty(self, v, record=None):
        return "%s%i" % (self.PREFIX, v)

    def parse(self, s):
        i = int(s)
        if 1 <= i <= self.MAX_VALUE:
            return i
        else:
            raise ValueError(i)

    def unparse(self, v):
        return str(v)

    @property
    def sql_expression(self):
        return f"date_part('{self.SQL_DATE_FIELD}', {self._sql_expression})::integer"


class YearLabelMixin:
    SUFFIX = "_year"
    DEFAULT_TITLE = "Year"
    DATETIME_FORMAT = "%Y"

    SQL_DATE_FIELD = "year"

    def classify(self, d):
        return date(d.year, 1, 1)

    def pretty(self, d, record=None):
        return d and ensure_unicode(d.year) or "Unknown"


class YearLabel(YearLabelMixin, DateTruncLabel):
    pass


class DatetimeYearLabel(YearLabelMixin, DatetimeTruncLabel):
    pass


class ISOYearLabel(DatetimePartLabel):
    SUFFIX = "_isoyear"
    DEFAULT_TITLE = "ISOYear"

    SQL_DATE_FIELD = "isoyear"
    MAX_VALUE = float("inf")
    PREFIX = "ISO"

    @staticmethod
    def classify(date):
        return date.isocalendar()[0]


class MonthLabelMixin:
    SUFFIX = "_month"
    DEFAULT_TITLE = "Month"
    FORMAT = "%Y-%m"

    SQL_DATE_FIELD = "month"

    def classify(self, d):
        return date(d.year, d.month, 1)

    def pretty(self, d, record=None):
        return d and d.strftime("%b\xA0%Y") or "Unknown"

    def parse(self, s):
        # parse -6 like "6 months ago"
        if _re_delta.match(s):
            today = date.today()
            nmonths = today.year * 12 + today.month - 1
            year, month = divmod(nmonths + int(s), 12)
            return date(year, month + 1, 1)
        else:
            return super().parse(s)


class MonthLabel(MonthLabelMixin, DateTruncLabel):
    pass


class DatetimeMonthLabel(MonthLabelMixin, DatetimeTruncLabel):
    pass


class MonthOfYearLabel(DatetimePartLabel):
    SUFFIX = "_moy"
    DEFAULT_TITLE = "MonthOfYear"

    SQL_DATE_FIELD = "month"
    MAX_VALUE = 12

    @staticmethod
    def pretty(m, record=None):
        return month_name[m]

    @staticmethod
    def classify(date):
        return date.month


class QuarterLabelMixin:
    SUFFIX = "_quarter"
    DEFAULT_TITLE = "Quarter"
    DATETIME_FORMAT = "%Y-%m"

    SQL_DATE_FIELD = "quarter"

    def classify(self, d):
        return date(d.year, ((d.month - 1) // 3 * 3) + 1, 1)

    def pretty(self, d, record=None):
        if not d:
            return "Unknown"
        quarter_num = (d.month - 1) // 3 + 1
        return f"Q{quarter_num}\xA0{d.year}"

    def parse(self, s):
        # parse -1 like "1 quarter ago"
        if _re_delta.match(s):
            return date_to_quarter(date.today(), int(s))
        else:
            d = super().parse(s)
            return self.classify(d)


class QuarterLabel(QuarterLabelMixin, DateTruncLabel):
    pass


class DatetimeQuarterLabel(QuarterLabelMixin, DatetimeTruncLabel):
    pass


class QuarterNumLabel(DatetimePartLabel):
    SUFFIX = "_quarternum"
    DEFAULT_TITLE = "QuarterNum"

    SQL_DATE_FIELD = "quarter"
    MAX_VALUE = 4
    PREFIX = "Q"

    @staticmethod
    def classify(date):
        return ((date.month - 1) // 3 * 3) + 1


class WeekLabelMixin:
    SUFFIX = "_week"
    DEFAULT_TITLE = "Week"
    FORMAT = "%Y-%m-%d"

    SQL_DATE_FIELD = "week"

    def classify(self, d):
        return d - timedelta(days=d.isoweekday() - 1)

    def pretty(self, d, record=None):
        if not d:
            return "Unknown"
        d1 = d - timedelta(days=d.isoweekday() - 1)
        d2 = d1 + timedelta(days=6)
        return f"{d1.strftime('%d %b')}..{d2.strftime('%d %b %Y')}"

    def parse(self, s):
        # parse -4 like "4 weeks ago"
        if _re_delta.match(s):
            day = date.today()
            day -= timedelta(days=day.isoweekday() - 1)  # first day of the week
            return day + timedelta(days=7 * int(s))
        else:
            return super().parse(s)


class WeekLabel(WeekLabelMixin, DateTruncLabel):
    pass


class DatetimeWeekLabel(WeekLabelMixin, DatetimeTruncLabel):
    pass


class ISOWeekNumLabel(DatetimePartLabel):
    """
    Use with ISOYearLabel, _not_ YearLabel!
    """

    SUFFIX = "_isoweeknum"
    DEFAULT_TITLE = "ISOWeekNum"

    SQL_DATE_FIELD = "week"
    MAX = 53
    PREFIX = "W"

    @staticmethod
    def classify(date):
        return date.isocalendar()[1]


class DayLabelMixin:
    SUFFIX = "_day"
    DEFAULT_TITLE = "Day"
    FORMAT = "%Y-%m-%d"

    SQL_DATE_FIELD = "day"

    def classify(self, d):
        return date(d.year, d.month, d.day)

    def pretty(self, d, record=None):
        return d and d.strftime("%a\xA0%Y-%m-%d") or "Unknown"

    def parse(self, s):
        # parse -30 like "30 days ago"
        if _re_delta.match(s):
            return date.today() + timedelta(days=int(s))
        else:
            return super().parse(s)

    def to_excel(self, value, record=None):
        return value


class DayLabel(DayLabelMixin, DateTruncLabel):
    """
    Note: this label does not do ::date typecast by default because doing so may
    sometimes prevent indexes from being used.   If you are dealing with a
    datetime sql expression, you need to override sql_expression to do this
    yourself, e.g.:

       sql_expression="main.cr_date::date"

    """

    @property
    def sql_expression(self):
        return self._sql_expression


class DatetimeDayLabel(DayLabelMixin, DatetimeTruncLabel):
    """
    Like DayLabel, but can be used for datetime sql expressions.
    """


class DOYLabel(DatetimePartLabel):
    SUFFIX = "_doy"
    DEFAULT_TITLE = "DayOfYear"

    SQL_DATE_FIELD = "doy"
    MAX_VALUE = 366
    PREFIX = "D"

    @staticmethod
    def classify(date):
        return date.isocalendar()[2]


class HourLabel(DatetimeTruncLabel):
    SUFFIX = "_hour"
    DEFAULT_TITLE = "Hour"
    DATETIME_FORMAT = "%Y-%m-%dT%H"

    SQL_DATE_FIELD = "hour"

    def classify(self, d):
        return datetime(d.year, d.month, d.day, hour=getattr(d, "hour", 0))

    def pretty(self, d, record=None):
        return d and d.strftime("%a\xA0%Y-%m-%dT%H") or "Unknown"

    def parse(self, s):
        # parse -30 like "30 hours ago"
        if _re_delta.match(s):
            return date.today() + timedelta(hours=int(s))
        else:
            return super().parse(s)


class WeekdayLabel(DatetimePartLabel):
    SUFFIX = "_weekday"
    DEFAULT_TITLE = "Weekday"

    SQL_DATE_FIELD = "isodow"
    MAX_VALUE = 7

    @staticmethod
    def pretty(d, record=None):
        return day_name[(d + 6) % 7]

    @staticmethod
    def classify(date):
        return date.isoweekday()


class MonthdayLabel(DatetimePartLabel):
    SUFFIX = "_monthday"
    DEFAULT_TITLE = "Monthday"

    SQL_DATE_FIELD = "day"
    MAX_VALUE = 31
    PREFIX = ""

    @staticmethod
    def classify(date):
        return date.day


class Measure(Label):
    """An accumulable (aggregatable) Label"""

    def __init__(self, name, cls="measure", show_by_default=True, **kwargs):
        if "acc" not in kwargs:
            kwargs["acc"] = accs.Sum
        super().__init__(name, cls=cls, **kwargs)
        self.show_by_default = show_by_default

    def add_sql_measure(self, sql):
        return self.acc.manipulate_sql(sql, self.name, self.sql_expression)


class AttributeMeasure(Measure, AttributeLabel):
    def __init__(self, name, **kwargs):
        if "none_value" not in kwargs:
            kwargs["none_value"] = ""
        super().__init__(name, **kwargs)


class AttributeRatioMeasure(AttributeMeasure):
    def __init__(
        self, name, attr_num, attr_denom, expr_num=None, expr_denom=None, **kwargs
    ):
        if "acc" not in kwargs:
            kwargs["acc"] = accs.RatioSum(
                attr_num, attr_denom, expr_num=expr_num, expr_denom=expr_denom
            )

        def ratio(record):
            num = getattr(record, attr_num, 0.0)
            den = getattr(record, attr_denom, 1.0)
            if num is None or den is None or den == 0:
                return None
            den = float(den)
            ratio = num / den
            if den < 0:
                return -ratio
            else:
                return ratio

        super().__init__(name, extract=ratio, **kwargs)
