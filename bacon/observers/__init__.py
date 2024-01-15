"""Bacon view base implementation.

TODO: rename this package to views: observer is a different pattern.

All observers have a name used to read the state from the environment (e.g.
the query from a web request, the size of a graph from a request option).
Configuration is passed as a Builder instance.

The observed model is a CuttingBoard instance, containing both the cube
definition and the data to be represented. Views should avoid to access the data
if not required, e.g. if we are building a web page and rendering a plot as
an <img> tag: we probably just need some metadata (e.g. the plot size) instead
of a data slice, which is required in the plot request instead.

Customer subclasses are expected to customize a few methods in order to add
filters or values to the query before/after manipulation by the builder.
Another subclassing direction is to provide concrete implementation of views,
e.g. a table, a plot. The two are mostly orthogonal, so if needed a customer
may provide a mixin with the report logic and use it to create CustomizedTable,
CustomizedPlot etc.
"""

from bacon.cubequery import CubeQuery
from bacon.cubenav import Navigator


class Controller:
    def __init__(self, name, builder, cutboard):
        self.name = name
        self.builder = builder
        self.cutboard = cutboard

        self._nav = Navigator(self.name, builder=self.builder, cubedef=cutboard.cubedef)

    @property
    def nav(self):  # TODO: rename to 'navigator'
        nav = self._nav
        if nav.query is None:
            nav.parse_query(self.make_query())
            assert nav.query is not None

        return nav

    @property
    def query(self):
        try:
            return self._q
        except AttributeError:
            self._q = self.get_query()
            return self._q

    @property
    def cubedef(self):
        return self.cutboard.cubedef

    def get_query(self):
        return self.nav.query

    def make_query(self):
        return CubeQuery()

    def finish_query(self, query):
        return query

    def get_slice(self, query=None):
        if query is None:
            query = self.finish_query(self.query)

        # Hack to work around Django swallowing some exceptions
        # resulting in empty tables instead of an useful traceback:
        # re-raise these exceptions as base Exception class.
        # The 3-params form of raise preserves the original traceback.
        try:
            return self.cutboard.slice(query)
        except (TypeError, AttributeError, KeyError) as e:
            raise Exception(f"{e.__class__.__name__}: {e}") from e

    def get_value(self, param):
        return self.builder.get_value(param)


class Viewer:
    def __init__(self, name, controller):
        self.name = name
        self.controller = controller

    def get_value(self, param):
        param = self.name + "-" + param if param else self.name
        return self.controller.get_value(param)

    def get_url(self, query, builder=None, params=None):
        if params is not None:
            mparams = {}
            for k, v in params.items():
                if k:
                    k = self.name + "-" + k
                else:
                    k = self.name
                mparams[k] = v

        else:
            mparams = None

        if builder is None:
            builder = self.controller.builder
        else:
            builder.cubedef = self.controller.cubedef

        return builder.get_url(query, self.controller.name, params=mparams)

    def get_query(self):
        return self.controller.query

    def finish_query(self, query):
        return self.controller.finish_query(query)

    @property
    def nav(self):
        return self.controller.nav

    def get_slice(self):
        query = self.get_query()
        query = self.finish_query(query)
        return self.controller.get_slice(query)

    def filter(self, query):
        return self.controller.cutboard.filter(query)
