"""Objects to build visualizations of query slices."""
from math import ceil
from itertools import chain

try:
    from itertools import izip
except ImportError:
    izip = zip
from collections import defaultdict

try:
    xrange
except NameError:
    xrange = range

from bacon import errors
from bacon.observers import Viewer
from bacon.cutting import LabeledValue
from bacon.cubenav import UrlMaker
from bacon.accumulators import Inconsistent
from collections import namedtuple
from bacon.utils import cache


class PaginatedViewer(Viewer):
    def __init__(self, name, controller, page_size=None, **kwargs):
        super().__init__(name, controller, **kwargs)
        self.page_size = page_size
        self._nrows = None

    @cache.cached_method
    def _parse_params(self):
        limit = self.page_size
        offset = 0
        nrows = None

        s = self.get_value("")
        if s:
            tokens = s.split(":")
            try:
                limit = int(tokens[0])
            except:
                pass

            try:
                offset = int(tokens[1])
            except:
                pass

            try:
                nrows = int(tokens[2])
            except:
                pass

        return limit, offset, nrows

    def get_limit(self):
        return self._parse_params()[0]

    def get_offset(self):
        _, offset, nrows = self._parse_params()

        if self._nrows and nrows and nrows != self._nrows:
            # this means that the number of pages in the dataset has changed
            # maybe for different filtering or axis selection
            # so start again from the first page.
            offset = 0

        return offset

    def current_page(self):
        return self.get_offset() // self.get_limit()

    def num_pages(self, nrows):
        if nrows is None:
            # arbitrary number to allow pages to show
            return 10
        limit = self.get_limit()
        if not limit:
            return 1  # no limit, so all on one page
        return int(ceil(nrows / limit))

    def pages(self, nrows):
        """Generate a sequence of page numbers to display for navigation.

        Generate tuples (label, number, is_current) as page links
        or (label, None, is_current) for static labels.
        """
        self._nrows = nrows

        npages = self.num_pages(nrows)
        if npages <= 1:
            return []
        curpage = self.current_page()

        def link(n):
            return (str(n + 1), n, False)

        def label(s, current=False):
            return (s, None, current)

        def run(start, end):
            if end - start < 7:
                for n in xrange(start, end):
                    yield link(n)
            else:
                for n in xrange(start, start + 2):
                    yield link(n)
                yield label("...")
                for n in xrange(end - 2, end):
                    yield link(n)

        return chain(
            [("\xab\xa0Prev", curpage - 1 if curpage else None, False)],
            run(0, curpage),
            [label(str(curpage + 1), True)],
            run(curpage + 1, npages),
            [("Next\xa0\xbb", curpage + 1 if curpage < npages - 1 else None, False)],
        )

    def to_string_page(self, n):
        """Return the query showing page n respect to the current query.

        Pages are 0-based. the "number" returned by `pages()` can be used.
        """
        query = self.get_query()
        limit, offset, nrows = self._parse_params()
        if limit:
            offset = n * limit
        if self._nrows:
            nrows = self._nrows

        params = {
            "": ":".join(
                str(x) if x is not None else "" for x in (limit, offset, nrows)
            )
        }

        return self.get_url(query, params=params)


class Table(PaginatedViewer):
    def __init__(self, name, controller, **kwargs):
        super().__init__(name, controller, **kwargs)
        self._widgets = defaultdict(list)

    def add_widget(self, widget, col_name=None):
        self._widgets[col_name].append(widget)


class RowWidget(object):
    def __init__(self, name, builder, label=None):
        self.name = name
        self.label = label or name
        self.builder = builder


# TODO: the things below are for rendering only, not for subclassing:
# this must be specified somehow


class BaseTableRenderer(object):
    def __init__(self, table):
        self.table = table
        self._nrows = 0

    def get_url(self, query):
        return self.table.get_url(query)

    @property
    def nav(self):
        return self.table.nav

    @property
    @cache.cached_method
    def query(self):
        # TODO: for external users maybe table.query should be finished
        return self.table.controller.finish_query(self.table.get_query())

    @property
    @cache.cached_method
    def slice(self):
        return self.table.get_slice()

    def pages(self):
        return self.table.pages(self._nrows)

    def record_values(self):
        try:
            return self._record_values
        except AttributeError:
            self._record_values = self.slice.record_values()
            return self._record_values

    def _limit_rows(self, rows):
        self.table._nrows = len(rows)
        limit = self.table.get_limit()
        if limit is None:
            return
        offset = self.table.get_offset()
        rows[:] = rows[offset : offset + limit]


class TableDetails(UrlMaker, BaseTableRenderer):
    """A table that doesn't aggregate but returns the original dataset."""

    def rows(self):
        from bacon.sql import RowsProxy

        rows = self.table.filter(self.query)

        # TODO: this smells like refactoring needed
        if isinstance(rows, RowsProxy):
            self._nrows = None  # we don't know how many are these
            limit = self.table.get_limit()
            if limit is None:
                return
            offset = self.table.get_offset()
            rows.set_page(limit, offset)
            return rows
        else:
            rows = list(rows)
            self._nrows = len(rows)
            self._limit_rows(rows)
            return iter(rows)

    def queryset(self):
        return self.table.filter(self.query)


class Table1D(UrlMaker, BaseTableRenderer):
    Row = namedtuple("Table1DRow", ["slice", "labels", "values"])

    def label_titles(self):
        try:
            return self._label_titles
        except AttributeError:
            self._slice_to_titles()
            return self._label_titles

    def value_titles(self):
        try:
            return self._value_titles
        except AttributeError:
            self._slice_to_titles()
            return self._value_titles

    def _slice_to_titles(self):
        self._label_titles = list(self.slice.axes_labels())
        self._value_titles = list(self.slice.value_labels())

    def has_no_column(self):
        return not (self.value_titles() or self.label_titles())

    def rows(self):
        self._totals = self.slice.make_acc()
        rows = [
            self.Row(slice, titles, list(self._iter_row(slice)))
            for titles, slice in self._rows(self.slice)
        ]

        self._nrows = len(rows)
        self._sort_rows(rows)
        self._limit_rows(rows)
        return iter(rows)

    def _sort_rows(self, rows):
        query = self.query
        if not query.order:
            return

        oname = query.order[0][1]
        try:
            self.slice.cubedef.get_measure(oname)
        except errors.DataError:
            return

        reverse = query.order[0][0] == "-"

        def key(triple):
            value = triple[0].record[oname].get()
            return value if value is not None else 0

        rows.sort(key=key, reverse=reverse)

    def _rows(self, slice, titles=()):
        if slice.dim:
            for t, ss in slice:
                for stuff in self._rows(ss, titles + (t,)):
                    yield stuff
        else:
            yield titles, slice

    def _iter_row(self, slice):
        record = slice.record
        if self._totals is not Inconsistent:
            try:
                for name in self.record_values():
                    self._totals[name] += record[name]
            except:
                # if one aggregate fails, remove all aggregates
                self._totals = Inconsistent

        for l in self.value_titles():
            yield LabeledValue(l, record[l.name].get(), record=record)

    def totals(self):
        try:
            tots = self._totals
        except AttributeError:
            # inefficient path, needed if s.b. calls totals before rows
            list(self.rows())
            tots = self._totals

        if tots is Inconsistent:
            return None

        if self._nrows > 1:
            return (
                LabeledValue(l, tots[l.name].get(), record=tots)
                for l in self.value_titles()
            )
        else:
            return ()

    def filter_query(self, slice):
        return self.nav.to_string(self.nav.filter(slice))

    @cache.cached_method
    def widget_titles(self):
        return sorted(self.table._widgets)


class TablePivot(UrlMaker, BaseTableRenderer):
    Row = namedtuple("Table2DRow", ["slice", "labels", "values", "totals"])

    def __init__(self, table):
        super().__init__(table)
        self.pivot_labels = list(self.nav.pivot)
        for l in self.pivot_labels:
            if not l.allow_pivot:
                raise errors.QueryError(f"can't pivot on {l.name}")

    # TODO: everything that is not a method needs being an attribute. Django
    # doesn't need braces but other observers do
    def label_titles(self):
        """
        The list of labels of the non-pivoted axes.

        All the axes are pivoted, return [None], as the table visualizers need
        a column anyway to put the titles of the pivoted values.
        """
        try:
            return self._label_titles
        except AttributeError:
            self._label_titles = []
            pivots = set(l.name for l in self.pivot_labels)
            for label in self.nav.axes:
                if label.name not in pivots:
                    self._label_titles.append(label)

            # We have to emit at least a column for alignment
            if not self._label_titles:
                self._label_titles.append(None)

            return self._label_titles

    def value_titles(self):
        """
        The list of values displayed in the table.

        These will be repeated into several groups of columns, one for every
        combination of pivoted values.

        """
        try:
            return self._value_titles
        except AttributeError:
            self._value_titles = list(self.slice.value_labels())
            return self._value_titles

    def pivot_titles(self):
        """
        Sequence of (pivot_label, pivoted_values) pairs.

        Each pair can be used in a table to display a row of titles: there is a
        row for every pivot axis and the pivoted_values contain the labeled
        values repeated as needed for alignment.

        """
        rv = zip(self.pivot_labels, zip(*self.pivot_lvs()))
        return rv

    def rows(self):
        self._totals = col_totals = [self.slice.make_acc() for i in self.pivot_lvs()]

        rows = []
        for titles, slice in self._rows(self.slice):
            if not titles:
                titles = (None,)  # for alignment
            row_totals = self.slice.make_acc()
            row = list(self._iter_row(slice, row_totals, col_totals))
            row_totals = [
                LabeledValue(l, row_totals[l.name].get(), record=row_totals)
                for l in self.value_titles()
            ]

            rows.append(self.Row(slice, titles, row, row_totals))

        self._nrows = len(rows)
        self._sort_rows(rows)
        self._limit_rows(rows)
        return iter(rows)

    def _sort_rows(self, rows):
        query = self.query
        if not query.order:
            return

        reverse, oname, values = query.order[0]
        reverse = reverse == "-"
        # position of the sort column in the values
        try:
            olabel = self.slice.cubedef.get_measure(oname)
        except errors.DataError:
            return
        try:
            imeas = self.value_titles().index(olabel)
        except ValueError:
            return

        if not values:
            # order by value in the totals column group
            def key(row):
                value = row.totals[imeas].value
                if value is None:
                    return 0
                return value

        else:
            # order by the value in the right pivot column group
            pvals = [tuple(lv.value for lv in lvs) for lvs in self.pivot_lvs()]
            try:
                ipivot = pvals.index(tuple(values))
            except ValueError:
                return

            imeas = ipivot * len(self.value_titles()) + imeas

            def key(row):
                value = row.values[imeas].value
                if value is None:
                    return 0
                return value

        rows.sort(key=key, reverse=reverse)

    def _rows(self, slice, titles=()):
        if slice.dim > len(self.query.pivot):
            for t, ss in slice:
                for stuff in self._rows(ss, titles + (t,)):
                    yield stuff
        else:
            yield titles, slice

    def _iter_row(self, slice, row_totals, col_totals):
        titles = self.value_titles()
        for labels, ctot in izip(self.pivot_lvs(), col_totals):
            tmp_slice = slice
            try:
                for label in labels:
                    tmp_slice = tmp_slice[label.value]
                record = tmp_slice.record
            except KeyError:
                record = self.slice.make_acc()

            for name in self.record_values():
                ra = record[name]
                row_totals[name] += ra
                ctot[name] += ra
            for l in titles:
                yield LabeledValue(l, record[l.name].get(), record=record)

    def filter_query(self, slice):
        return self.nav.to_string(self.nav.filter(slice))

    def pivot_lvs(self):
        try:
            return self._pivot_labels
        except AttributeError:
            self._pivot_labels = list(self.slice.iter_lvs(self.pivot_labels))
            return self._pivot_labels

    def totals(self):
        try:
            totals = self._totals
        except AttributeError:
            # inefficient path, needed if s.b. calls totals before rows
            list(self.rows())
            totals = self._totals

        if self._nrows > 1:
            return self._iter_totals(totals)
        else:
            return ()

    def _iter_totals(self, col_totals):
        titles = self.value_titles()
        tbl_tots = self.slice.make_acc()
        for tots in col_totals:
            for name, a in tots.items():
                tbl_tots[name] += a
            for l in titles:
                yield LabeledValue(l, tots[l.name].get(), record=tots)

        for l in titles:
            yield LabeledValue(l, tbl_tots[l.name].get(), record=tbl_tots)

    @cache.cached_method
    def widget_titles(self):
        return sorted(self.table._widgets)
