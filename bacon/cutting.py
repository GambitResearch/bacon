"""Define what a cutting board and a slice are."""
import re
import operator
from copy import copy, deepcopy
from functools import wraps

from threading import RLock
from collections import defaultdict, deque

from bacon import errors
from bacon.utils.eval import clean_whitespaces as dedent
from bacon.utils.synchro import synchro_method
from bacon.utils import cache

import logging

logger = logging.getLogger("bacon.cutting")
logger.setLevel(logging.INFO)


class CuttingBoard:
    """Allows observing a dataset according to the rules defined by a cubedef.

    `dataset` can be any iterable of python object, or callable returning one.
    Iterables or callable will be consumed when there is the need, and the
    result is cached in the object. Lists are used as they are, not copied:
    changing them in place for the outside is a bad idea.

    The ``CuttingBoard`` also keep a cache of results in order to generate
    slices without reading the complete dataset if possible.
    """

    # these classes implement ways to use the data of a pre-existing slices
    # to create a new slice.
    reuse_strategies = []

    def __init__(self, cubedef, dataset):
        self.cubedef = cubedef
        self._dataset = dataset

        # cache for already computed slices
        # Most recently used slices at the left
        self._slices = deque()

        # To synchronize access to _slices
        self._lock = RLock()

    def slice(self, query):
        """Create a new `Slice` from the dataset according to a `CubeQuery`.

        The *query* must be compatible with the `dataset`.
        """
        slice = self._get_cached_slice(query)
        if slice is not None:
            return slice
        else:
            slice = self._make_slice(query)
            self._cache_slice(slice)
            return slice

    def filter(self, query):
        """Return a subset of the dataset."""
        # Consume now the dataset if it is lazy.
        dataset = self._get_dataset()

        # Filter the dataset if required
        filter_p = _make_filter_predicate(query, self.cubedef)
        if filter_p is not None:
            dataset = filter(filter_p, dataset)

        return dataset

    def _make_slice(self, query):
        """Create a new `Slice` from the dataset according to a `CubeQuery`."""
        slice = self._make_empty_slice(query)

        # Consume now the dataset if it is lazy.
        dataset = self._get_dataset()

        # Filter the dataset if required
        filter_p = _make_filter_predicate(query, self.cubedef)
        if filter_p is not None:
            dataset = filter(filter_p, dataset)

        return self._fill_slice(slice, query, dataset)

    def _fill_slice(self, slice, query, dataset):
        # accumulate data into a labels -> acc mapping
        bins = defaultdict(slice._zero_f)
        acc_f = slice._acc_f
        key_f = slice._key_f
        for r in dataset:
            acc_f(bins[key_f(r)], r)

        # convert the above mapping in a nested dictionary.
        # TODO: if it works, i should accumulate directly in this structure.
        root = {}
        if query.dim:
            ii = range(query.dim - 1)
            for k in bins:
                d = root
                for i in ii:
                    x = k[i]
                    try:
                        d = d[x]
                    except KeyError:
                        d[x] = {}
                        d = d[x]

                d[k[-1]] = bins[k]
        else:
            root = bins[()]

        slice._data = root
        logger.debug(f"NEW: slice {slice._ident} for query {query.__dict__}")
        return slice

    def _make_empty_slice(self, query):
        """Create an empty slice with all the metadata to represent a query."""
        return _make_empty_slice(query, cubedef=self.cubedef)

    def _get_dataset(self):
        """Return the dataset: consume a lazy one if required."""
        ds = self._dataset
        if isinstance(ds, list):
            return ds

        if callable(ds):
            ds = ds()

        if not isinstance(ds, list):
            ds = list(ds)

        self._dataset = ds
        return ds

    @synchro_method("_lock")
    def _get_cached_slice(self, qnew):
        """Return a slice from the cache if available.

        The query can be obtained by manipulation of cached slices.
        """
        plans = []
        cost = None

        logger.debug("LOOKUP: %r", qnew.__dict__)
        for rs in self.reuse_strategies:
            rs = rs(qnew)
            for i, sold in enumerate(self._slices):
                if rs.is_compatible(sold):
                    cost = rs.estimate_cost(slice)
                    plans.append((cost, i, rs, sold))

                    # We don't need to watch further: we have an optimal query
                    if cost == 1:
                        del plans[:-1]
                        break

            # We don't need to watch further: we have an optimal strategy
            if cost == 1:
                break

        if not plans:
            logger.debug("MISS: %r", qnew.__dict__)
            return

        cost, i, rs, sold = min(plans)
        snew = rs.create_slice(sold)
        logger.debug(
            "HIT: slice %s created from %s by %s for query %r"
            % (snew._ident, sold._ident, rs.__class__.__name__, qnew.__dict__)
        )

        # Promote the reused slice and eventually add the new slice to the cache
        self._promote_cached_slice(i)
        if snew is not self._slices[0]:
            self._cache_slice(snew)

        return snew

    @synchro_method("_lock")
    def _cache_slice(self, slice):
        if len(self._slices) > 20:  # TODO: make this configurable
            old = self._slices.pop()
            logger.debug(
                "PURGED: slice %s for query %r", old._ident, old.query.__dict__
            )

        self._slices.appendleft(slice)

    @synchro_method("_lock")
    def _promote_cached_slice(self, i):
        """Flag the i-th item in the queue as just used."""
        if i == 0:
            return

        # Put the i-th element at the left
        d = self._slices
        d.rotate(-i)
        item = d.popleft()
        d.rotate(i)
        d.appendleft(item)


class SliceReuseStrategy:
    """Interface for strategies to use slices to create new slices."""

    def __init__(self, query):
        # The query we want to create a slice for
        self.query = query

    def is_compatible(self, slice):
        """Return True if *slice* is useful to create a slice for our query."""
        raise NotImplementedError

    def estimate_cost(self, slice):
        """Estimate the number of steps required to create the new slice.

        Assume *slice* is compatible.
        """
        raise NotImplementedError

    def create_slice(self, slice):
        """Return a new Slice instance starting from *slice*.

        Assume *slice* is compatible.
        """
        raise NotImplementedError

    @cache.cached_method
    def _get_values_in_slice(self):
        return set(_get_values_in_slice(self.query))


class ReuseCachedSlice(SliceReuseStrategy):
    """Allow to reuse a slice for the same query."""

    def is_compatible(self, slice):
        qnew = self.query
        qold = slice.query

        # check the axes are the same
        if qold.axes != qnew.axes:
            logger.debug("cache NOMATCH: axes:   %r", qold.__dict__)
            return False

        # Check the filters.
        # Because they are ANDed, I don't care about the order
        if sorted(qold.filters) != sorted(qnew.filters):
            logger.debug("cache NOMATCH: filters: %r", qold.__dict__)
            return False

        # Check the columns/hidden columns.
        if not self._get_values_in_slice() <= set(_get_values_in_slice(qold)):
            logger.debug("cache NOMATCH: values: %r", qold.__dict__)
            return False

        # sweet, we have found a slice we can recycle!
        logger.debug("cache MATCH: %r", qold.__dict__)
        return True

    def estimate_cost(self, slice):
        return 1

    def create_slice(self, slice):
        nslice = _make_empty_slice(self.query, cubedef=slice.cubedef)
        nslice._data = slice._data
        return nslice


CuttingBoard.reuse_strategies.append(ReuseCachedSlice)


class DrillOnFirstAxis(SliceReuseStrategy):
    """Kicks in when the user clicks on a value in the first axis."""

    def is_compatible(self, slice):
        qnew = self.query
        qold = slice.query

        # check we are adding a new filter
        if len(qold.filters) + 1 != len(qnew.filters):
            logger.debug("drill NOMATCH: number of filters: %r", qold.__dict__)
            return False

        nfilters = set(qnew.filters) - set(qold.filters)
        if len(nfilters) != 1:
            logger.debug("drill NOMATCH: added filters: %r", qold.__dict__)
            return False

        # Check the filter is on the first axis
        label, op, value = nfilters.pop()
        if not qold.axes or qold.axes[0] != label or op != "eq":
            logger.debug(
                "drill NOMATCH: new filter not on first axis: %r", qold.__dict__
            )
            return False

        # check the axes match
        if qold.axes[1:] != qnew.axes:
            logger.debug("drill NOMATCH: axes:   %r", qold.__dict__)
            return False

        # Check the columns/hidden columns.
        if not self._get_values_in_slice() <= set(_get_values_in_slice(qold)):
            logger.debug("drill NOMATCH: values: %r", qold.__dict__)
            return False

        # we can work on this slice
        logger.debug("drill MATCH: %r", qold.__dict__)
        return True

    def estimate_cost(self, slice):
        return 1

    def create_slice(self, slice):
        # Get the filter we want
        qnew = self.query
        qold = slice.query
        label, op, value = (set(qnew.filters) - set(qold.filters)).pop()

        # drill down one level
        try:
            data = slice._data[value]
        except KeyError:
            data = {}

        nslice = _make_empty_slice(self.query, cubedef=slice.cubedef)
        nslice._data = data
        return nslice


CuttingBoard.reuse_strategies.append(DrillOnFirstAxis)


class ManipulateSlice(SliceReuseStrategy):
    """Manipulate a slice cells to create a new slice.

    This strategy can create a new slice for an old one if the old slice
    is more granular or has the same granularity as the new one.

    It can also apply more restrictive filter, but only if entire cells of
    the old slice get filtered away.
    """

    def is_compatible(self, slice):
        qnew = self.query
        qold = slice.query

        # Check axis compatibility
        oaxes = set(qold.axes)
        if not oaxes >= set(qnew.axes):
            logger.debug("manip NOMATCH: axes:   %r", qold.__dict__)
            return False

        # Check the filters.
        # Accept a query more strict if the new filters are on axis
        ofilters = set(qold.filters)
        nfilters = set(qnew.filters)
        if not nfilters >= ofilters:
            logger.debug("manip NOMATCH: filters not compatible: %r", qold.__dict__)
            return False

        for name, op, value in nfilters - ofilters:
            if name not in oaxes:
                logger.debug("manip NOMATCH: filter on non axis: %r", qold.__dict__)
                return False

        # Check the columns/hidden columns.
        if not self._get_values_in_slice() <= set(_get_values_in_slice(qold)):
            logger.debug("manip NOMATCH: values: %r", qold.__dict__)
            return False

        # we can work on this slice
        logger.debug("manip MATCH: %r", qold.__dict__)
        return True

    def estimate_cost(self, slice):
        # TODO: the cost is the number of cells in the slice,
        # but for the moment it's only interesting that it is > 1.
        return 10

    def create_slice(self, slice):
        fkey = self._make_new_key_f(slice)
        filter_p = self._make_filter_predicate(slice)

        ds = self._unroll(slice)
        if filter_p is not None:
            ds = filter(filter_p, ds)

        bins = {}
        for okey, acc in ds:
            nkey = fkey(okey)
            try:
                oacc = bins[nkey]
            except KeyError:
                bins[nkey] = deepcopy(acc)
            else:
                for name in oacc:
                    oacc[name] += acc[name]

        # TODO: exactly the same xform in CuttingBoard._make_slice()
        # refactor/getridof/whatever
        root = {}
        if self.query.dim:
            ii = range(self.query.dim - 1)
            for k in bins:
                d = root
                for i in ii:
                    x = k[i]
                    try:
                        d = d[x]
                    except KeyError:
                        d[x] = {}
                        d = d[x]

                d[k[-1]] = bins[k]
        else:
            root = bins[()]

        nslice = _make_empty_slice(self.query, cubedef=slice.cubedef)
        nslice._data = root
        return nslice

    def _make_new_key_f(self, slice):
        """Create a function to map label tuples from the old to the new query.

        We assume the two queries are compatible as it was checked upstream.
        """
        qnew = self.query
        qold = slice.query

        # indexes of the new query axes in the old one
        idxs = list(map(qold.axes.index, qnew.axes))

        # itemgetter(i1, i2, ...) returns a tuple
        # but we need to special-case 1 and 0 arguments
        # (resp. returning a scalar and a raspberry)
        if len(idxs) > 1:
            fkey = operator.itemgetter(*idxs)

        elif len(idxs) == 1:

            def fkey(key, g=operator.itemgetter(idxs[0])):
                return (g(key),)

        else:  # len(idxs) == 0

            def fkey(key):
                return ()

        return fkey

    def _make_filter_predicate(self, slice):
        """Return a predicate to filter on the unrolled slice."""
        qnew = self.query
        qold = slice.query

        idxs = []
        ops = []
        vs = []
        for name, op, value in qnew.filters:
            if (name, op, value) in qold.filters:
                # the slice is already filtered on this value
                continue

            try:
                op = _op_map[op]
            except KeyError:
                raise errors.QueryError(f"unknown operator: '{op}'")

            # we know for compatibility that the filter is on one of the slice axes
            idxs.append(qold.axes.index(name))
            ops.append(op)
            vs.append(value)

        if not idxs:
            return None

        L = len(idxs)
        assert L == len(ops) == len(vs)

        d = locals()
        exec(
            dedent(
                """
		def p(kv, %(idxs)s, %(vs)s, %(ops)s):
			key = kv[0]
			return %(ps)s
		"""
                % {
                    "idxs": ", ".join("idx%d=idxs[%d]" % (i, i) for i in range(L)),
                    "vs": ", ".join("v%d=vs[%d]" % (i, i) for i in range(L)),
                    "ops": ", ".join("op%d=ops[%d]" % (i, i) for i in range(L)),
                    "ps": " and ".join(
                        "op%d(key[idx%d], v%d)" % (i, i, i) for i in range(L)
                    ),
                }
            ),
            d,
        )
        p = d["p"]

        return p

    def _unroll(self, slice):
        """Unroll a nested dict into a (key, acc) sequence."""
        dim = slice.dim

        def _unroll(key, tree):
            if len(key) == dim - 1:
                for k, v in tree.items():
                    yield key + (k,), v
            else:
                for k, v in tree.items():
                    for i in _unroll(key + (k,), v):
                        yield i

        return _unroll((), slice._data)


CuttingBoard.reuse_strategies.append(ManipulateSlice)


class Slice:
    """Accumulation in a dataset's values along some of its labels."""

    _lock = RLock()
    _n = 0

    def __init__(self, data, cubedef, query):
        self._data = data
        self.cubedef = cubedef
        self.query = query
        self.dim = query.dim

        self._key_f = _make_key_function(query, cubedef)
        self._zero_f, self._acc_f = _make_acc_function(query, cubedef)

        with Slice._lock:
            self._ident = f"s-{Slice._n}"
            Slice._n += 1

    def __repr__(self):
        return f"<{self.__class__.__name__} dim={self.dim} at 0x{id(self):08X}>"

    def __getitem__(self, idx):
        """Remove one of the slice axes.

        Return a reduced slice if the slice dimension is > 0: this allows
        reaching single values using a syntax such ``slice[row][col].record``.
        """
        if self.dim > 0:
            rv = copy(self)
            rv._data = self._data[idx]
            rv.dim = self.dim - 1
            return rv

        raise KeyError("can't slice further a 0 dimension slice: use '.record' instead")

    def __iter__(self):
        """Iterate over the innermost dimension of the dataset."""
        if self.dim:
            iaxis = self.query.dim - self.dim
            name = self.query.axes[iaxis]
            label = self.cubedef.get_label(name)
            values = list(self._data)
            values.sort(key=label.key, reverse=label.reverse)
            for v in values:
                yield LabeledValue(label, v), self[v]

        else:
            raise KeyError(
                "can't iterate over a 0 dimension slice: use '.record' instead"
            )

    def cls(self):
        if self.dim == 0:
            return self.cubedef.cls(self.record)

        return ""

    def axes_labels(self):
        return (self.cubedef.get_label(v) for v in self.query.axes)

    def value_labels(self):
        return (self.cubedef.get_measure(v) for v in self.query.values)

    def record_values(self):
        """Return the name of the values used to create the internal records.

        This includes values defined hidden in the cubedef but not the ones
        hidden by the user.
        """
        return _get_values_in_slice(self.query)

    def iter_lvs(self, labels):
        axes = self.query.axes
        idxs = set(axes.index(l.name) for l in labels)
        values = set()

        def _gather_lvs(data, key=(), level=0):
            if level >= len(axes):
                return
            l1 = level + 1
            if level in idxs:
                for k, d in data.items():
                    newkey = key + (k,)
                    if len(newkey) == len(idxs):
                        values.add(newkey)
                    _gather_lvs(d, newkey, l1)
            else:
                for d in data.values():
                    _gather_lvs(d, key, l1)

        _gather_lvs(self._data)
        values = list(values)

        # Sort is stable, so sort from the rightmost key
        il = list(enumerate(labels))
        il.reverse()
        for i, l in il:
            key = lambda vs: l.key(vs[i])
            values.sort(key=key, reverse=l.reverse)

        for vs in values:
            yield [LabeledValue(l, v) for l, v in zip(labels, vs)]

    def iter_record(self):
        record = self.record
        return (
            LabeledValue(l, record[l.name].get(), record=record)
            for l in self.value_labels()
        )

    @property
    def record(self):
        if self.dim == 0:
            return self._data

        raise AttributeError("record not available on a %d dimension slice" % self.dim)

    def make_acc(self):
        """Create an accumulator compatible with the slice."""
        return self._zero_f()


class LabeledValue:
    __slots__ = ["label", "value", "record"]

    def __init__(self, label, value, record=None):
        self.label = label
        self.value = value
        self.record = record

    def __repr__(self):
        return "%s(value=%r, label=%r, record=%r)" % (
            self.__class__.__name__,
            self.value,
            self.label,
            self.record,
        )

    @property
    def filter_op(self):
        return self.label.get_filter_op()

    @property
    def title(self):
        return self.label.title

    @property
    def pretty(self):
        return self.label.pretty(self.value, record=self.record)

    @property
    def cls(self):
        return self.label.cls(self.value, self.record)

    def __unicode__(self):
        return str(self.pretty)

    def __str__(self):
        return str(self.pretty)

    @property
    def excel(self):
        return self.label.to_excel(self.value, record=self.record)


def _make_empty_slice(query, cubedef):
    """Create an empty slice with all the metadata to represent a query."""
    return Slice(None, cubedef=cubedef, query=query)


def _make_key_function(query, cubedef):
    """Create a function that produce the axes from the data."""
    labels = [cubedef.get_label(a) for a in query.axes]
    extract_fs = [l.extract for l in labels]
    return lambda record: tuple(f(record) for f in extract_fs)


def _make_acc_function(query, cubedef):
    names = _get_values_in_slice(query)
    labels = list(map(cubedef.get_measure, names))
    code = dedent(
        """
	def zero_f(%(accs)s):
		return {%(items)s}
	"""
        % {
            "accs": ", ".join(
                "a%d=labels[%d].acc" % (i, i) for i in range(len(labels))
            ),
            "items": ", ".join(
                "%r: a%d()" % (label.name, i) for i, label in enumerate(labels)
            ),
        }
    )
    d = locals()
    exec(code, d)
    zero_f = d["zero_f"]

    if labels:
        exec(
            dedent(
                """
	def acc_f(acc, record, %(es)s):
%(adds)s
	"""
                % {
                    "es": ", ".join(
                        "e%d=labels[%d].extract" % (i, i) for i in range(len(labels))
                    ),
                    "adds": "\n".join(
                        "\t\tacc[%r].add(e%d(record), record)" % (label.name, i)
                        for i, label in enumerate(labels)
                    ),
                }
            ),
            d,
        )
        acc_f = d["acc_f"]
    else:
        # Do this with a lambda and the python compiler will barf
        def acc_f(acc, record):
            pass

    return zero_f, acc_f


def _get_values_in_slice(query):
    """Return the names of the values to be included in a slice.

    the values in a query can be hidden for two different reasons:

    a.	values added with query.add_value(..., visible=False)
            are used for further classification, e.g. a ccy_code value
            helps summing monies with consistent currency; a weekday
            value can be used to highlight the weekinds in the report etc.
    b.	values hidden in the query.hidden_values are the ones the user
            has chosen to skip

    The _make_acc_function creates accumulators containing values
    hidden for b. because the hidden values are presumibly used
    by some value that may be visible. It doesn't include the
    hidden_values instead.
    """
    hidden = query.hidden_values
    return [n for n in query.all_values if n not in hidden]


# map operators from the query representation to python syntax.


def is_in(a, b):
    return a in b


def is_not_in(a, b):
    return a not in b


# This is ugly, as we can't check the difference between
# None, {} and {''}. We assume no-one wants to search for the latter,
# and make searching for None the same as searching for empty.
# See Merge request 21 for more discussion.
def make_set(item):
    if item is None:
        return set()
    elif type(item) is not set or "" in item:
        newset = set(item)
        newset.discard("")
        return newset
    else:
        return item


def setop(f):
    @wraps(f)
    def inner(a, b):
        return f(make_set(a), make_set(b))

    return inner


@setop
def hasall(a, b):
    return a.issuperset(b)


@setop
def hasany(a, b):
    return not a.isdisjoint(b)


@setop
def hasnone(a, b):
    return a.isdisjoint(b)


@setop
def hasonly(a, b):
    return a == b


@setop
def issubset(a, b):
    return a.issubset(b)


@setop
def issuperset(a, b):
    return a.issuperset(b)


@setop
def disjoint(a, b):
    return a.isdisjoint(b)


def ismatch(a, b):
    return (a is not None) and re.compile(b).search(a)


_op_map = {
    "eq": operator.eq,
    "ne": operator.ne,
    "gt": operator.gt,
    "ge": operator.ge,
    "lt": operator.lt,
    "le": operator.le,
    "in": is_in,
    "ni": is_not_in,
    "hasall": hasall,
    "hasnone": hasnone,
    "hasany": hasany,
    "hasonly": hasonly,
    "hasnotall": lambda a, b: not hasall(a, b),
    "subsetof": issubset,
    "notsubsetof": lambda a, b: not issubset(a, b),
    "supersetof": issuperset,
    "notsupersetof": lambda a, b: not issuperset(a, b),
    "disjointfrom": disjoint,
    "intersects": lambda a, b: not disjoint(a, b),
    "equals": hasonly,
    "notequals": lambda a, b: not hasonly(a, b),
    "match": ismatch,
    "nmatch": lambda a, b: not ismatch(a, b),
}


def _make_filter_predicate(query, cubedef):
    es = []
    ops = []
    vs = []
    for name, op, value in query.filters:
        try:
            op = _op_map[op]
        except KeyError:
            raise errors.QueryError(f"unknown operator: '{op}'")

        es.append(cubedef.get_label(name).extract)
        ops.append(op)
        vs.append(value)

    if not es:
        return None

    L = len(es)
    assert L == len(ops) == len(vs)

    d = locals()
    exec(
        dedent(
            """
	def p(record, %(es)s, %(vs)s, %(ops)s):
		return %(ps)s
	"""
            % {
                "es": ", ".join("e%d=es[%d]" % (i, i) for i in range(L)),
                "vs": ", ".join("v%d=vs[%d]" % (i, i) for i in range(L)),
                "ops": ", ".join("op%d=ops[%d]" % (i, i) for i in range(L)),
                "ps": " and ".join(
                    "op%d(e%d(record), v%d)" % (i, i, i) for i in range(L)
                ),
            }
        ),
        d,
    )
    p = d["p"]

    return p
