from bacon.builders import QueryBuilder
from bacon import errors
from bacon.utils.strings import (
    bsescape,
    bsunescape,
    bssplit,
    ensure_unicode,
    quote_plus,
)
from bacon.constants import MULTI_ARG_OPS


def encode_query(q):
    """Encode a query from dict to url snippet.

    q can be a dictionary or a lists multidict (as django QueryDict is).
    """
    rv = []
    for k, vv in q.items():
        k = quote_plus(k)
        if isinstance(vv, list):
            for v in vv:
                rv.append(f"{k}={quote_plus(v, safe=':/')}")
        else:
            rv.append(f"{k}={quote_plus(vv, safe=':/')}")

    return "&".join(rv)


class UrlQueryBuilder(QueryBuilder):
    """Specific parser to have the query represented as an URL.

    The url may appear as the path, the query or the fragment of the url.
    The commands in a query are separated by '/', the tokens in each command
    are separated by ':'. Such characters are backslash-escaped if they appear
    in any token. The resulting string is *not* percent-encoded: the task is
    left to a caller.
    """

    # constants defining where the queries are expected to be found in the URL.
    IN_QUERY = "IN_QUERY"
    IN_PATH = "IN_PATH"
    IN_FRAGMENT = "IN_FRAGMENT"

    def __init__(
        self, context, cubedef=None, base_url=None, query_location=IN_QUERY, **kwargs
    ):
        """The context should be a parameters mapping."""
        super(UrlQueryBuilder, self).__init__(context, cubedef, **kwargs)
        self.base_url = base_url if base_url is not None else "."
        self.query_dict = context
        self.query_location = query_location

    def tokenize(self, name):
        query = self.get_query_string(name) or ""
        for chunk in bssplit(query, "/"):
            if not chunk:
                continue

            tokens = bssplit(chunk, ":")
            cmd = tokens.pop(0)
            if not hasattr(self, cmd):
                raise errors.QueryError(f"unknown command: '{cmd}'")

            yield cmd, list(map(bsunescape, tokens))

    def v(self, query, name):
        return query.add_value(name)

    def hv(self, query, name):
        return query.hide_value(name)

    def a(self, query, name):
        return query.add_axis(name)

    def p(self, query, name):
        return query.set_pivot(name)

    def f(self, query, *args):
        # the filter syntax is
        # f:LABEL:OP:VALUE1[:VALUE2...]
        # f:LABEL:VALUE (implies OP = eq)

        if len(args) == 2:
            name, value = args
            op = "eq"

        elif len(args) == 3:
            name, op, value = args
            if op in MULTI_ARG_OPS:
                value = (value,)

        elif len(args) >= 3:
            name, op = args[:2]
            value = args[2:]

            if op not in MULTI_ARG_OPS:
                raise errors.QueryError(
                    "bad number of arguments for operator '%s': %d"
                    % (op, len(args) - 2)
                )

        else:
            raise errors.QueryError(
                f"bad number of arguments for a filter: {len(args)}"
            )

        # i have name, op, value here
        # value is a tuple for MULTI_ARG_OPS, a string for the others

        label = self.cubedef.get_label(name)
        if isinstance(value, tuple):
            value = frozenset(label.parse(ensure_unicode(v)) for v in value)
        else:
            value = label.parse(ensure_unicode(value))

        return query.add_filter(name, value, operator=op)

    def o(self, query, name, *args):
        values = []
        if args and query.pivot:
            for value, axis in zip(args, query.pivot):
                label = self.cubedef.get_label(axis)
                values.append(label.parse(value))

        return query.order_by(name, values)

    def l(self, query, limit=None, offset=0):
        # not used anymore but don't break the urls
        return query

    def get_query_string(self, name):
        if (
            self.query_location == self.IN_QUERY
            or self.query_location == self.IN_FRAGMENT
        ):
            # The server doesn't receive the fragment in the request.
            # we assume we are using this builder to generate ajax urls,
            # so we expect to find them in the query.
            q = self.query_dict
            return q.get(name)

        elif self.query_location == self.IN_PATH:
            raise NotImplementedError

        else:
            raise ValueError(
                f"unexpected value for query_location: {self.query_location!r}"
            )

    # TODO: merge to_string and get_url
    def get_url(self, query, name, params=None):
        s = self.to_string(query, name)

        q = self.query_dict.copy()
        q[name] = s
        if params is not None:
            # TODO: can't use q.update(params) because django query dict appends values
            for k, v in params.items():
                q[k] = v

        if self.query_location == self.IN_QUERY:
            return self.base_url + "?" + encode_query(q)

        elif self.query_location == self.IN_FRAGMENT:
            return self.base_url + "#" + encode_query(q)

        elif self.query_location == self.IN_PATH:
            raise NotImplementedError

        else:
            raise ValueError(
                f"unexpected value for query_location: {self.query_location!r}"
            )

    def to_string(self, query, name):
        return "/".join(self._to_string_iter(query))

    def _to_string_iter(self, query):
        for name, op, value in query.filters:
            label = self.cubedef.get_label(name)
            if op not in MULTI_ARG_OPS:
                value = self._encode(label.unparse(value))
            elif value is None:
                value = ""
            else:
                value = ":".join(self._encode(label.unparse(v)) for v in value)

            # an ugly way to generate f:NAME:OP:VALUE or f:NAME:VALUE if OP is 'eq'
            if op == "eq":
                op = ":"
            else:
                op = ":" + op + ":"

            yield f"f:{str(name)}{str(op)}{value}"

        pivot = query.pivot
        for name in query.axes:
            if name not in pivot:
                yield "a:" + str(name)
            else:
                yield "p:" + str(name)

        for name in query.values:
            yield "v:" + str(name)

        for name in query.hidden_values:
            yield "hv:" + str(name)

        for sign, name, values in query.order:
            snips = ["o"]
            snips.append("-" + str(name) if sign == "-" else str(name))
            if values and pivot:
                for value, axis in zip(values, pivot):
                    label = self.cubedef.get_label(axis)
                    value = label.unparse(value)
                    snips.append(self._encode(value))

            yield ":".join(snips)

    def _encode(self, s):
        """Escape unsafe characters with backslashes.

        Unsafe means in the context of the query language, i.e. if we use
        ',' as separator, the ',' can't be in a value. The result is usually
        urlquotes to make the returned string valid in an url.
        """
        s = ensure_unicode(s)
        return bsescape(s, "/:")

    def get_value(self, param):
        return self.get_query_string(param)
