from __future__ import absolute_import

from django.conf.urls.defaults import *  # noqa

from . import views

urlpatterns = patterns(
    "",
    (r"^$", views.navigation_html),
    url(r"^time_sales.png$", views.time_sales_png, name="time_sales_png"),
)
