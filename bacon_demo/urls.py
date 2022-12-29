from django.conf import settings
from django.conf.urls import include, patterns
from django.shortcuts import redirect

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

urlpatterns = patterns(
    "",
    (r"^$", lambda r: redirect("/sales/")),
    (r"^sales/", include("bacon_demo.bacon_sales.urls")),
    (r"^sales-ajax/", include("bacon_demo.sales_ajax.urls")),
    (
        r"^static/(.*)$",
        "django.views.static.serve",
        {"document_root": settings.PROJECT_DIR + "/static"},
    ),
)
