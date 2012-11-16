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
    url(r'^users/$', views.UserList.as_view(), name='user-list'),
    url(r'^users/(?P<pk>[0-9]+)/$', views.UserDetail.as_view(), name='user-detail'),
    url(r'^groups/$', views.GroupList.as_view(), name='usergroup-list'),
    url(r'^groups/(?P<pk>[0-9]+)/$', views.GroupDetail.as_view(), name='usergroup-detail'),
    url(r'^locations/$', views.LocationList.as_view(), name='location-list'),
    url(r'^locations/(?P<pk>[^/]+)/$', views.LocationDetail.as_view(), name='location-detail'),
    url(r'^timeseries/$', views.TimeseriesList.as_view(), name='timeseries-list'),
    url(r'^timeseries/(?P<pk>[^/]+)/$', views.TimeseriesDetail.as_view(), name='timeseries-detail'),
    url(r'^timeseries/(?P<pk>[^/]+)/data/$', views.TimeseriesData.as_view(), name='timeseries-data'),
#    url(r'^read/', views.api_response),
#    url(r'^write/', views.api_write),
    )

urlpatterns += patterns('',
    url(r'^auth/', include('rest_framework.urls', namespace='rest_framework'))
)

urlpatterns += debugmode_urlpatterns()
