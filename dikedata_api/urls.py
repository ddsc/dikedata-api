# (c) Nelen & Schuurmans.  MIT licensed, see LICENSE.rst.
from django.conf.urls.defaults import include
from django.conf.urls.defaults import patterns
from django.conf.urls.defaults import url
from django.contrib import admin
from lizard_ui.urls import debugmode_urlpatterns

from dikedata_api import views

admin.autodiscover()

urlpatterns = patterns(
    '',
    url(r'^read/', views.api_response),
    url(r'^write/', views.api_write),
    )
urlpatterns += debugmode_urlpatterns()
