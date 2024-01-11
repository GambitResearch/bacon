"""Object to accumulate values"""
from math import sqrt


class Accumulator(object):
    def add(self, v, record):
        raise NotImplementedError

    def get(self):
        raise NotImplementedError

    def __iadd__(self, other):
        raise NotImplementedError

    @classmethod
    def manipulate_sql(self, query, column, expression):
        raise NotImplementedError


class Sum(Accumulator):
    __slots__ = ["acc"]

    def __init__(self):
        self.acc = None

    def add(self, v, record):
        if self.acc is not None:
            if v is not None:
                self.acc += v
        else:
            self.acc = v

    def get(self):
        return self.acc

    def __iadd__(self, other):
        if self.acc is not None:
            if other.acc is not None:
                self.acc += other.acc
        else:
            self.acc = other.acc

        return self

    def __repr__(self):
        return f"<{self.__class__.__name__} ({self.acc!r}) at 0x{id(self):08X}>"

    @classmethod
    def manipulate_sql(self, sql, column, expression):
        return sql.add_aggregate(column, f"sum({expression})")


class Union(Accumulator):
    __slots__ = ["acc", "included_empty"]

    def __init__(self):
        self.acc = None
        self.included_empty = False

    def _set_from(self, new_val):
        if self.acc and new_val:
            self.acc = self.acc.union(new_val)
        elif new_val:
            self.acc = new_val
        else:
            self.included_empty = True

    def add(self, v, _record):
        self._set_from(v)

    def __iadd__(self, other):
        self._set_from(other.acc)
        return self

    def get(self):
        return self.acc, self.included_empty


class Max(Accumulator):
    __slots__ = ["acc"]

    def __init__(self):
        self.acc = None

    def add(self, v, record):
        if self.acc is not None:
            if v > self.acc:
                self.acc = v
        else:
            self.acc = v

    def get(self):
        return self.acc

    def __iadd__(self, other):
        if self.acc is not None:
            if other.acc is not None:
                self.acc = max(self.acc, other.acc)
        else:
            self.acc = other.acc

        return self

    def __repr__(self):
        return f"<{self.__class__.__name__} ({self.acc!r}) at 0x{id(self):08X}>"


class Min(Accumulator):
    __slots__ = ["acc"]

    def __init__(self):
        self.acc = None

    def add(self, v, record):
        if self.acc is not None:
            if v < self.acc:
                self.acc = v
        else:
            self.acc = v

    def get(self):
        return self.acc

    def __iadd__(self, other):
        if self.acc is not None:
            if other.acc is not None:
                self.acc = min(self.acc, other.acc)
        else:
            self.acc = other.acc

        return self

    def __repr__(self):
        return f"<{self.__class__.__name__} ({self.acc!r}) at 0x{id(self):08X}>"


class Count(Accumulator):
    __slots__ = ["acc"]

    def __init__(self):
        self.acc = 0

    def add(self, v, record):
        self.acc += 1

    def get(self):
        return self.acc

    def __iadd__(self, other):
        self.acc += other.acc
        return self

    def __repr__(self):
        return f"<{self.__class__.__name__} ({self.acc!r}) at 0x{id(self):08X}>"


class Average(Accumulator):
    __slots__ = ["n", "acc"]

    def __init__(self):
        self.n = 0
        self.acc = None

    def add(self, v, record):
        self.n += 1
        if self.acc is not None:
            if v is not None:
                self.acc += v
        else:
            self.acc = v

    def get(self):
        if self.n:
            return self.acc / self.n
        else:
            return None

    def __iadd__(self, other):
        if self.acc is not None:
            if other.acc is not None:
                self.acc += other.acc
        else:
            self.acc = other.acc

        self.n += other.n

        return self

    def __repr__(self):
        return f"<{self.__class__.__name__} ({self.n!r} items) at 0x{id(self):08X}>"


class StdDev(Accumulator):
    """Accumulator to calculate the std dev of a sequence of numbers.

    Algorightm for incremental calculation of stddev described in Donald Knuth's
    "The Art of Computer Programming, Volume 2: Seminumerical Algorithms",
    section 4.2.2 attributed to B.P. Welford, Technometrics, 4,(1962), 419-420

    see http://mathcentral.uregina.ca/QQ/database/QQ.09.02/carlos1.html
    """

    __slots__ = ["n", "m", "s"]

    def __init__(self):
        self.n = 0

    def add(self, v, record):
        if self.n:
            k = self.n + 1
            m1 = self.m
            self.m = m1 + (v - m1) / k
            self.s += (v - m1) * (v - self.m)
        else:
            k = 1
            self.m = v
            self.s = 0

        self.n = k

    def get(self):
        if self.n > 1:
            return sqrt(self.s / (self.n - 1))
        else:
            return None

    def __iadd__(self, other):
        return Inconsistent

    def __repr__(self):
        return f"<{self.__class__.__name__} ({self.n!r} items) at 0x{id(self):08X}>"


class _Unused(Accumulator):
    def __repr__(self):
        return "Unused"


Unused = _Unused()  # singleton


class _Inconsistent(Accumulator):
    def add(self, v, record):
        pass

    def get(self):
        return None

    def __iadd__(self, other):
        return self

    def __repr__(self):
        return "Inconsistent"


Inconsistent = _Inconsistent()  # singleton


class Group(Accumulator):
    __slots__ = ["val"]

    def __init__(self):
        self.val = Unused

    def add(self, v, record, Unused=Unused, Inconsistent=Inconsistent):
        if self.val is Unused:
            self.val = v
        elif self.val is Inconsistent:
            pass
        elif self.val != v:
            self.val = Inconsistent

    def get(self, Unused=Unused, Inconsistent=Inconsistent):
        if not (self.val is Inconsistent or self.val is Unused):
            return self.val
        else:
            return None

    def __iadd__(self, other, Unused=Unused, Inconsistent=Inconsistent):
        if self.val is Inconsistent:
            pass
        elif self.val is Unused:
            self.val = other.val

        elif other.val is Inconsistent:
            self.val = Inconsistent
        elif other.val is Unused:
            pass

        elif self.val != other.val:
            self.val = Inconsistent

        return self

    def __repr__(self):
        return f"<{self.__class__.__name__} ({self.val!r}) at 0x{id(self):08X}>"


def LabeledAcc(getter, acc):
    class LabeledAcc_(Accumulator):
        __slots__ = ["acc", "label"]

        def __init__(self):
            self.acc = acc()
            self.label = Unused

        def add(self, v, record, Unused=Unused, Inconsistent=Inconsistent):
            if self.label is Unused:
                self.label = getter(record)
                self.acc.add(v, record)
                return

            elif self.acc is Inconsistent:
                return

            label = getter(record)
            if self.label == label:
                self.acc.add(v, record)
            else:
                self.acc = Inconsistent

        def get(self):
            return self.acc.get()

        def __iadd__(self, other, Unused=Unused, Inconsistent=Inconsistent):
            if self.acc is Inconsistent:
                return self
            elif other.acc is Inconsistent:
                self.acc = Inconsistent
                return self

            if other.label is Unused:
                return self
            elif self.label is Unused:
                self.label = other.label

            if self.label == other.label:
                self.acc += other.acc
            else:  # self.label != other.label:
                self.acc = Inconsistent

            return self

        def __repr__(self):
            return "<%s (%r, %r) at 0x%08X>" % (
                "LabeledAcc",
                self.label,
                self.acc,
                id(self),
            )

    return LabeledAcc_


def RatioSum(attr_num, attr_denom, expr_num=None, expr_denom=None):
    class RatioSum_(Accumulator):
        __slots__ = ["accs", "attrs"]

        def __init__(self):
            self.accs = {}

        def add(self, v, record):
            for attr, default in ((attr_num, 0.0), (attr_denom, 1.0)):
                nv = getattr(record, attr, default) or 0.0
                self.accs[attr] = self.accs.get(attr, 0.0) + nv

        def get(self):
            num = self.accs.get(attr_num, 0.0)
            denom = self.accs.get(attr_denom, 1.0)
            if num is None or denom is None or denom == 0.0:
                return None
            return num / denom

        def __iadd__(self, other):
            if self.accs is not None:
                if other.accs is not None:
                    for k, v in other.accs.items():
                        self.accs[k] = self.accs.get(k, 0.0) + other.accs[k]
            else:
                self.accs = other.accs.copy()

            return self

        def __repr__(self):
            return f"<{self.__class__.__name__} ({self.accs!r}) at 0x{id(self):08X}>"

        @classmethod
        def manipulate_sql(self, sql, column, expression):
            sql = sql.add_aggregate(attr_num, "sum(%s)" % (expr_num or attr_num))
            sql = sql.add_aggregate(attr_denom, "sum(%s)" % (expr_denom or attr_denom))
            return sql

    return RatioSum_
