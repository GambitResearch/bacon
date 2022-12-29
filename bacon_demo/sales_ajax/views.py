from django.shortcuts import render_to_response
from django.template.context import RequestContext
from django.core.urlresolvers import reverse

from bacon_demo.data import sales_cubedef, sales_dataset
from bacon.cutting import CuttingBoard

from bacon.django.builder import DjangoQueryBuilder

from bacon_demo.bacon_sales.views import SalesTable, SalesPlot


def navigation_ajax(request):
    return render_to_response(
        "sales_ajax/navigation.html", context_instance=RequestContext(request)
    )


def nav(request):
    cd = sales_cubedef()
    ds = None
    cb = CuttingBoard(cd, ds)
    b = DjangoQueryBuilder(request, cd, query_location=DjangoQueryBuilder.IN_FRAGMENT)
    table = SalesTable("q", b, cb)
    return render_to_response("bacon/nav.tmpl", {"table": table})


def table(request):
    cd = sales_cubedef()
    ds = sales_dataset()
    cb = CuttingBoard(cd, ds)
    b = DjangoQueryBuilder(request, cd, query_location=DjangoQueryBuilder.IN_FRAGMENT)
    table = SalesTable("q", b, cb)
    return render_to_response("bacon/table.tmpl", {"table": table})


def plot(request):
    cd = sales_cubedef()
    ds = None
    cb = CuttingBoard(cd, ds)
    b = DjangoQueryBuilder(request, cd, base_url=reverse("time_sales_png"))
    plot = SalesPlot("q", b, cb, size=(800, 500))  # TODO: cutboard optional?
    return render_to_response("bacon/plot_tag.tmpl", {"plot": plot})
