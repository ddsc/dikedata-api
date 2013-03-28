# (c) Nelen & Schuurmans.  MIT licensed, see LICENSE.rst.
from django.conf.urls.defaults import include
from django.conf.urls.defaults import patterns
from django.conf.urls.defaults import url
from django.contrib import admin
from django.views.generic.simple import redirect_to
from lizard_ui.urls import debugmode_urlpatterns


admin.autodiscover()

urlpatterns = patterns(
    '',
    url(r'^$', redirect_to, {'url': 'v1'}),
    url(r'^v1/', include('dikedata_api.urls_v1'), name='v1'),
    url(r'^auth/', include('rest_framework.urls', namespace='rest_framework'))
)

urlpatterns += debugmode_urlpatterns()
