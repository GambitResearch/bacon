"""A type of cutting board that can query the database in a smart way"""

from copy import deepcopy
from functools import wraps

import psycopg2
import psycopg2.extras

from bacon.cutting import CuttingBoard

import logging

logger = logging.getLogger("bacon.sql")
logger.setLevel(logging.DEBUG)

try:
    basestring
except NameError:
    basestring = str, bytes


class SqlQuery(object):
    def __init__(self):
        self._prequerylist = []
        self._ctelist = []
        self._selectlist = []
        self._fromlist = []
        self._wherelist = []
        self._grouplist = []
        self._orderlist = []
        self._args = []
        self._limit = None
        self._offset = None

        self._ctes = set()
        self._sources = set()
        self._columns = set()

    def quote_ident(self, ident):
        """Return the given string suitably quoted to be used as an identifier
        in an SQL statement string, similar to Postgres' quote_ident function."""
        # http://www.postgresql.org/message-id/87ei3zsr3j.fsf@comcast.net

        # https://github.com/postgres/postgres/blob/c62736cc37f6812d1ebb41ea5a86ffe60564a1f0/src/backend/utils/adt/ruleutils.c#L8459
        return '"' + ident.replace('"', '""') + '"'

    def add_prequery(self, query):
        # useful to cripple the parser with 'set enable_mergejoin to off' and
        # such. Please use "set local" to keep it local to the transaction!
        if not query.rstrip().endswith(";"):
            query += ";"
        sql = deepcopy(self)
        if query not in self._prequerylist:
            sql._prequerylist.append(query)
        return sql

    def add_from(self, name, expression):
        if name in self._sources:
            return self

        sql = deepcopy(self)
        sql._fromlist.append(expression)
        sql._sources.add(name)
        return sql

    def add_cte(self, name, expression):
        if name in self._ctes:
            return self

        sql = deepcopy(self)
        sql._ctelist.append(expression)
        sql._ctes.add(name)
        return sql

    def add_group(self, column, expression):
        if column in self._columns:
            return self

        sql = deepcopy(self)
        sql._columns.add(column)
        sql._selectlist.append(f"({expression}) AS {self.quote_ident(column)}")
        sql._grouplist.append(expression)
        return sql

    def add_order(self, expression):
        sql = deepcopy(self)
        sql._orderlist.append(expression)
        return sql

    def add_aggregate(self, column, expression):
        if column in self._columns:
            return self

        sql = deepcopy(self)
        sql._columns.add(column)
        sql._selectlist.append(f"({expression}) AS {self.quote_ident(column)}")
        return sql

    def add_filter(self, expression, *values):
        sql = deepcopy(self)
        sql._wherelist.append(expression)
        sql._args.extend(values)
        return sql

    def set_limit(self, limit):
        sql = deepcopy(self)
        sql._limit = limit
        return sql

    def set_offset(self, offset):
        sql = deepcopy(self)
        sql._offset = offset
        return sql

    def get_query(self):
        if not self._selectlist:
            return None

        query = []

        query.extend(self._prequerylist)

        if self._ctelist:
            query.extend(["WITH", ",\n".join(self._ctelist)])

        query.extend(
            [
                "SELECT",
                ",\n".join(self._selectlist),
                "FROM",
                "\n".join(self._fromlist),
            ]
        )

        if self._wherelist:
            query.extend(
                [
                    "WHERE",
                    "\nAND ".join(self._wherelist),
                ]
            )

        if self._grouplist:
            query.extend(
                [
                    "GROUP BY",
                    ",\n".join(self._grouplist),
                ]
            )

        if self._orderlist:
            query.extend(
                [
                    "ORDER BY",
                    ",\n".join(self._orderlist),
                ]
            )

        if self._limit is not None:
            query.append("LIMIT %s")
        if self._offset is not None:
            query.append("OFFSET %s")

        query = "\n".join(query)
        return query

    def __repr__(self):
        return "<bacon.sql.SqlQuery: %s, %r>" % (
            self.get_query().replace("\n", "  "),
            self.get_args(),
        )

    def get_args(self):
        args = self._args[:]
        if self._limit is not None:
            args.append(self._limit)
        if self._offset is not None:
            args.append(self._offset)
        return args


class BaseConnectionFactory(object):
    """An abstract object returning and disposing database connections."""

    def getconn(self):
        raise NotImplementedError

    def putconn(self, conn):
        raise NotImplementedError


class ConnectionFactory(BaseConnectionFactory):
    """An object returning and disposing psycopg connections.

    dsn can be either a dict or a string.
    """

    def __init__(self, dsn):
        self.dsn = dsn

    def getconn(self):
        if isinstance(self.dsn, basestring):
            return psycopg2.connect(self.dsn)
        else:
            return psycopg2.connect(**self.dsn)

    def putconn(self, conn):
        conn.close()


def with_connection_method(f):
    @wraps(f)
    def with_connection_method_(self, *args, **kwargs):
        cnn = self.connection_factory.getconn()
        try:
            return f(self, cnn, *args, **kwargs)
        finally:
            self.connection_factory.putconn(cnn)

    return with_connection_method_


class SqlCuttingBoard(CuttingBoard):
    """A cutting board that can query the database for a reduced dataset"""

    def __init__(self, cubedef, sql, connection_factory):
        self.cubedef = cubedef
        self.sql = sql
        self.connection_factory = connection_factory

        super().__init__(cubedef, dataset=())

    @with_connection_method
    def _make_slice(self, cnn, query):
        sql = self.manipulate_sql(self.sql, query)

        cur = cnn.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)
        sql_query, sql_args = sql.get_query(), sql.get_args()
        logger.debug("query sql:\n%s\nquery args: %r", sql_query, sql_args)
        if sql_query is not None:
            cur.execute(sql_query, sql_args)

        slice = self._make_empty_slice(query)

        if sql_query is not None:
            return self._fill_slice(slice, query, cur)
        else:
            return slice

    def manipulate_sql(self, sql, query):
        for axis in query.axes:
            label = self.cubedef.get_label(axis)
            sql = label.add_sql_sources(sql)
            sql = label.add_sql_label(sql)

        # uglyness goes on and on. Include values shown and values added with
        # visible=False (e.g. when ccy is added as value because filtering on
        # it) but not the values hidden by the user.
        # TODO: ccy_code is probably to be added as hidden label, not value
        for value in set(query.all_values) - set(query.hidden_values):
            measure = self.cubedef.get_measure(value)
            sql = measure.add_sql_sources(sql)
            sql = measure.add_sql_measure(sql)

        for axis, op, value in query.filters:
            label = self.cubedef.get_label(axis)
            sql = label.add_sql_sources(sql)
            sql = label.add_sql_filter(sql, op, value)

        return sql

    def filter(self, query):
        sql = deepcopy(self.sql)
        sql._selectlist = ["*"]
        for axis, op, value in query.filters:
            label = self.cubedef.get_label(axis)
            sql = label.add_sql_sources(sql)
            sql = label.add_sql_filter(sql, op, value)

        return RowsProxy(self.connection_factory, sql)


class DjangoCuttingBoard(CuttingBoard):
    """
    A cutting board that can use Django Q objects for a reduced dataset

    To be used with labels which are initialised with the following params:

    django_expression which is a django Q object or a string representing the attribute name

    django_fields (optional)
    If provided this overrides django_expression as what is passed to .only on the query when slicing

    django_select_related is a list of strings to be added to select_related when slicing
    django_prefetch_related is a list of strings to be added to prefetch_related when slicing
    """

    def __init__(self, cubedef, queryset):
        self.cubedef = cubedef
        self.queryset = queryset
        self.only = set()
        self.select_related = set()
        self.prefetch_related = set()
        super().__init__(cubedef, dataset=())

    def _add_label(self, label):
        for select_related in label.django_select_related:
            self.select_related.add(select_related)
        for prefetch_related in label.django_prefetch_related:
            self.prefetch_related.add(prefetch_related)
        if label.django_fields:
            for field in label.django_fields:
                self.only.add(field)
        elif isinstance(label.django_expression, str):
            self.only.add(label.django_expression)

    def _add_labels(self, query):
        for axis in query.axes:
            self._add_label(self.cubedef.get_label(axis))

        for value in set(query.all_values) - set(query.hidden_values):
            measure = self.cubedef.get_measure(value)
            self._add_label(measure)

        for axis, op, value in query.filters:
            self._add_label(self.cubedef.get_label(axis))

    def _make_slice(self, query):
        slice = self._make_empty_slice(query)
        queryset = self.filter(query)
        self._add_labels(query)
        queryset = queryset.only(*self.only)
        queryset = queryset.select_related(*self.select_related)
        queryset = queryset.prefetch_related(*self.prefetch_related)
        return self._fill_slice(slice, query, queryset)

    def filter(self, query):
        queryset = self.queryset
        for axis, op, value in query.filters:
            label = self.cubedef.get_label(axis)
            queryset = label.add_q_filter(queryset, op, value)
        return queryset


class RowsProxy(object):
    """A container to return a list of result still supporting pagination

    Used for the interaction with a DetailsTable.
    """

    def __init__(self, connection_factory, sql):
        self.connection_factory = connection_factory
        self.sql = sql
        self.limit = self.offset = None

    def __iter__(self):
        return iter(self._iter())

    def set_page(self, limit, offset):
        self.limit = limit
        self.offset = offset

    @with_connection_method
    def _iter(self, cnn):
        sql = self.sql
        if self.limit is not None:
            sql = sql.set_limit(self.limit)
        if self.offset is not None:
            sql = sql.set_offset(self.offset)

        sql_query, sql_args = sql.get_query(), sql.get_args()
        logger.debug("query sql:\n%s\nquery args: %r", sql_query, sql_args)
        cur = cnn.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)
        cur.execute(sql_query, sql_args)
        return cur.fetchall()
