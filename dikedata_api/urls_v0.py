# (c) Nelen & Schuurmans.  MIT licensed, see LICENSE.rst.
from dikedata_api import views
from django.conf.urls.defaults import patterns
from django.conf.urls.defaults import url


urlpatterns = patterns(
    '',
    url(r'^users/?$',
        views.UserList.as_view(),
        name='user-list'),
    url(r'^users/(?P<pk>[0-9]+)/?$',
        views.UserDetail.as_view(),
        name='user-detail'),
    url(r'^groups/?$',
        views.GroupList.as_view(),
        name='usergroup-list'),
    url(r'^groups/(?P<pk>[0-9]+)/?$',
        views.GroupDetail.as_view(),
        name='usergroup-detail'),
    url(r'^roles/?$',
        views.RoleList.as_view(),
        name='role-list'),
    url(r'^roles/(?P<pk>[0-9]+)/?$',
        views.RoleDetail.as_view(),
        name='role-detail'),
    url(r'^datasets/?$',
        views.DataSetList.as_view(),
        name='dataset-list'),
    url(r'^datasets/(?P<pk>[^/]+)/?$',
        views.DataSetDetail.as_view(),
        name='dataset-detail'),
    url(r'^dataowner/?$',
        views.DataOwnerList.as_view(),
        name='dataowner-list'),
    url(r'^dataowner/(?P<pk>[^/]+)/?$',
        views.DataOwnerDetail.as_view(),
        name='dataowner-detail'),
    url(r'^locations/?$',
        views.LocationList.as_view(),
        name='location-list'),
    url(r'^locations/(?P<uuid>[^/]+)/?$',
        views.LocationDetail.as_view(),
        name='location-detail'),
    url(r'^timeseries/?$',
        views.TimeseriesList.as_view(),
        name='timeseries-list'),
    url(r'^timeseries/(?P<uuid>[^/]+)/?$',
        views.TimeseriesDetail.as_view(),
        name='timeseries-detail'),
    url(r'^events/?$',
        views.MultiEventList.as_view(),
        name='multi-event-list'),
    url(r'^events/(?P<uuid>[^/]+)/?$',
        views.EventList.as_view(),
        name='event-list'),
    url(r'^events/(?P<uuid>[^/]+)/(?P<dt>[^/]+)/?$',
        views.EventDetail.as_view(),
        name='event-detail'),
    url(r'^parameters/?$',
        views.ParameterList.as_view(),
        name='parameter-list'),
    url(r'^parameters/(?P<pk>[^/]+)/?$',
        views.ParameterDetail.as_view(),
        name='parameter-detail'),
    url(r'^logicalgroups/?$',
        views.LogicalGroupList.as_view(),
        name='logicalgroup-list'),
    url(r'^logicalgroups/(?P<pk>[^/]+)/?$',
        views.LogicalGroupDetail.as_view(),
        name='logicalgroup-detail'),
    url(r'^alarms/?$',
        views.AlarmList.as_view(),
        name='alarm-list'),
    url(r'^alarms/(?P<pk>[^/]+)/?$',
        views.AlarmDetail.as_view(),
        name='alarm-detail'),
    url(r'^alarms/(?P<pk>[^/]+)/?$',
        views.AlarmDetail.as_view(),
        name='alarm_active-detail'),
)
