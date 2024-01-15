from django.shortcuts import render_to_response
from django.template.context import RequestContext
from django.core.urlresolvers import reverse

from bacon_demo.data import sales_cubedef, sales_dataset
from bacon.cutting import CuttingBoard
from bacon.observers.plot import TimePlotData
from bacon.observers.tables import Table

from bacon.django.builder import DjangoQueryBuilder
from bacon.django.plot import render_figure


class SalesTable(Table):
    def finish_query(self, query):
        b = self.builder
        query = b.add_value(query, "units")
        query = b.add_value(query, "amount")
        return query


class SalesPlot(TimePlotData):
    def get_query(self):
        q = super().get_query()

        for name in q.pivot:
            q = q.unset_pivot(name)
        for name in q.axes:
            q = q.remove_axis(name)

        assert q.dim == 0

        for name in q.hidden_values:
            q = q.show_value(name)

        return q

    def finish_query(self, query):
        b = self.builder
        query = self.builder.add_axis(query, "creation_date_day")
        query = b.add_value(query, "amount")
        return query

    def make_plot(self, fig):
        ax = fig.add_subplot(111)

        x = self.get_time_axis()
        y = self.get_attr_axis("amount")
        ax.plot_date(x, y, "-")

        from matplotlib.dates import DateFormatter

        ax.xaxis.set_major_formatter(DateFormatter("%Y-%m-%d"))
        fig.autofmt_xdate()


def navigation_html(request):
    cd = sales_cubedef()
    ds = sales_dataset()
    cb = CuttingBoard(cd, ds)
    table = SalesTable("q", DjangoQueryBuilder(request, cd), cb)
    plot = SalesPlot(
        "q",
        DjangoQueryBuilder(request, cd, base_url=reverse("time_sales_png")),
        cb,
        size=(800, 500),
    )

    return render_to_response(
        "bacon_sales/navigation.html",
        {"table": table, "plot": plot},
        context_instance=RequestContext(request),
    )


def time_sales_png(request):
    cd = sales_cubedef()
    ds = sales_dataset()
    cb = CuttingBoard(cd, ds)
    b = DjangoQueryBuilder(request, cd)
    plot = SalesPlot("q", b, cb, size=(800, 500))

    return render_figure(request, plot.make_figure())
