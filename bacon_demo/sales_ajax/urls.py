from __future__ import absolute_import

from django.conf.urls import patterns

from . import views

urlpatterns = patterns('',
	(r'^$', views.navigation_ajax),
	(r'^nav$', views.nav),
	(r'^table$', views.table),
	(r'^plot$', views.plot),
)
