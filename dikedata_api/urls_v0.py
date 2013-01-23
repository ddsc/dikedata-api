# (c) Nelen & Schuurmans.  MIT licensed, see LICENSE.rst.
from dikedata_api import views
from django.conf.urls.defaults import patterns
from django.conf.urls.defaults import url


urlpatterns = patterns(
    '',
    url(r'^users/$',
        views.UserList.as_view(),
        name='user-list'),
    url(r'^users/(?P<pk>[0-9]+)/$',
        views.UserDetail.as_view(),
        name='user-detail'),
    url(r'^groups/$',
        views.GroupList.as_view(),
        name='usergroup-list'),
    url(r'^groups/(?P<pk>[0-9]+)/$',
        views.GroupDetail.as_view(),
        name='usergroup-detail'),
    url(r'^roles/$',
        views.RoleList.as_view(),
        name='role-list'),
    url(r'^roles/(?P<pk>[0-9]+)/$',
        views.RoleDetail.as_view(),
        name='role-detail'),
    url(r'^datasets/$',
        views.DataSetList.as_view(),
        name='dataset-list'),
    url(r'^datasets/(?P<pk>[^/]+)/$',
        views.DataSetDetail.as_view(),
        name='dataset-detail'),
    url(r'^locations/$',
        views.LocationList.as_view(),
        name='location-list'),
    url(r'^locations/(?P<code>[^/]+)/$',
        views.LocationDetail.as_view(),
        name='location-detail'),
    url(r'^timeseries/$',
        views.TimeseriesList.as_view(),
        name='timeseries-list'),
    url(r'^timeseries/(?P<code>[^/]+)/$',
        views.TimeseriesDetail.as_view(),
        name='timeseries-detail'),
    url(r'^events/(?P<code>[^/]+)/$',
        views.EventList.as_view(),
        name='event-list'),
)
