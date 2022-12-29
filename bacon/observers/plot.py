from __future__ import division

from operator import itemgetter

from bacon.observers import Viewer


class Plot(Viewer):
    def __init__(self, name, controller, size=(640, 480), dpi=80, **kwargs):
        super(Plot, self).__init__(name, controller, **kwargs)
        self.size = size
        self.dpi = dpi

    def _make_figure(self):
        from matplotlib.figure import Figure

        w, h = self.size
        dpi = self.dpi
        return Figure(figsize=(w / dpi, h / dpi), dpi=dpi)

    def make_figure(self):
        f = self._make_figure()
        self.make_plot(f)
        return f

    def make_plot(self, fig):
        raise NotImplementedError

    # TODO: this belongs to a template tag
    @property
    def url(self):
        return self.get_url(self.get_query())


class TimePlotData(Plot):
    def __init__(self, name, controller, **kwargs):
        super(TimePlotData, self).__init__(name, controller, **kwargs)

    def _make_data(self):
        if hasattr(self, "_t"):
            return

        slice = self.get_slice()

        if slice.dim != 1:
            raise ValueError("only 1d slices for now.")

        measures = list(slice.value_labels())

        data = list((l.value, ss.record) for l, ss in slice)

        if not data:
            raise ValueError("no data found: what should I do?")

        data.sort()
        self._t = list(map(itemgetter(0), data))

        values = list(map(itemgetter(1), data))
        self._x = dict(
            (m.name, [a.get() for a in map(itemgetter(m.name), values)])
            for m in measures
        )

        return data

    def get_time_axis(self):
        self._make_data()
        return self._t

    def get_attr_axis(self, attr):
        self._make_data()
        return self._x[attr]
