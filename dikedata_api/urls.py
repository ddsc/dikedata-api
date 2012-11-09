# (c) Nelen & Schuurmans.  MIT licensed, see LICENSE.rst.
from dikedata_api import views
from django.conf.urls.defaults import include
from django.conf.urls.defaults import patterns
from django.conf.urls.defaults import url
from django.contrib import admin
from lizard_ui.urls import debugmode_urlpatterns
from rest_framework.urlpatterns import format_suffix_patterns


admin.autodiscover()

urlpatterns = patterns('',
    url(r'^$', views.Root.as_view()),
    url(r'^observers/$', views.ObserverList.as_view(), name='observer-list'),
    url(r'^observers/(?P<pk>[^/]+)/$', views.ObserverDetail.as_view(), name='observer-detail'),
#    url(r'^read/', views.api_response),
#    url(r'^write/', views.api_write),
    )
urlpatterns += debugmode_urlpatterns()
