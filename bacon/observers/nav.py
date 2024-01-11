from datetime import date

from bacon.observers import Viewer


class NavPanel(Viewer):
    """A container for `NavWidget` to be rendered on an interface."""

    def __init__(self, name, controller, widgets=None, **kwargs):
        super().__init__(name, controller, **kwargs)
        self.widgets = widgets or []


class NavWidget:
    """An object displayed in a `NavPanel` allowing customised navigation."""

    def __init__(self, label):
        self.label = label


class DatesRangeWidget(NavWidget):
    """A widget showing two dates allowing to select a range."""

    def __init__(self, label, axis, toolkit="prototype"):
        supported = ("jquery", "prototype")
        if toolkit not in supported:
            raise ValueError("toolkit not supported: %s", toolkit)

        super().__init__(label)
        # axis is the name of one of the axis in the time dimension to handle
        # it should be rendered as a date (yyyy-mm-dd), so day or week is fine.
        self.axis = axis
        self.toolkit = toolkit

    def get_urls(self, panel):
        """Return a list of urls with templates of queries.

        The urls are:

        - no value
        - only start value
        - only end value
        - both values

        The parameters have ``__from__`` and ``__to__`` placeholders in place
        which the code using the widget should fill in with the input data

        """
        urls = []

        q0 = panel.nav.remove_dimension_filters(self.axis)
        urls.append(panel.get_url(q0))

        q1 = q0.add_filter(self.axis, date(8192, 1, 1), operator="ge")
        urls.append(panel.get_url(q1).replace("8192-01-01", "__from__"))

        q2 = q0.add_filter(self.axis, date(8192, 12, 31), operator="le")
        urls.append(panel.get_url(q2).replace("8192-12-31", "__to__"))

        q3 = q1.add_filter(self.axis, date(8192, 12, 31), operator="le")
        urls.append(
            panel.get_url(q3)
            .replace("8192-01-01", "__from__")
            .replace("8192-12-31", "__to__")
        )

        return urls


class StringFilterWidget(NavWidget):
    """A widget allowing to filter on an axis."""

    def __init__(self, label, axis, op="eq"):
        super().__init__(label)
        self.axis = axis
        self.op = op

    def get_urls(self, panel):
        """Return a tuple of urls with templates of queries.

        The urls are:
        - no value
        - with value

        """

        q0 = panel.nav.remove_dimension_filters(self.axis)
        q1 = q0.add_filter(self.axis, "__PLACEHOLDER__", self.op)
        return panel.get_url(q0), panel.get_url(q1)


class ButtonsWidget(NavWidget):
    """A widget container for `Button`."""

    def __init__(self, label, buttons):
        super().__init__(label)
        self.buttons = buttons


class Button:
    """A button redirecting to a new query when clicked."""

    def __init__(self, label, image_url=None, builder=None):
        self.label = label
        self.image_url = image_url
        self.builder = builder

    def get_query(self, panel):
        return panel.get_query()

    def get_url(self, widget, panel):
        query = self.get_query(panel)
        return panel.get_url(query, builder=self.builder)


class FixedQueryButton(Button):
    """A button that returns always the same query."""

    def __init__(self, label, query, **kwargs):
        super().__init__(label, **kwargs)
        self._query = query

    def get_url(self, widget, panel):
        return panel.get_url(self._query)


class FilterButton(Button):
    """A button that changes a filter value on a query."""

    REMOVE = "__REMOVE__"

    def __init__(self, label, axis, value, **kwargs):
        super().__init__(label, **kwargs)
        self.axis = axis
        self.value = value

    def get_query(self, panel):
        query = panel.nav.query.remove_filter(self.axis)
        if self.value != self.REMOVE:
            query = query.add_filter(self.axis, self.value)

        return query
