# (c) Nelen & Schuurmans.  MIT licensed, see LICENSE.rst.
from __future__ import unicode_literals

from ddsc_core.models import LocationGroup, Location, Timeseries
from dikedata_api import serializers
from datetime import datetime
from dateutil.relativedelta import relativedelta
from dikedata_api.exceptions import APIException
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.models import User, Group as Role
from django.http import Http404
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from lizard_ui.views import UiView
from lizard_security.models import DataSet, UserGroup
from lizard_security.backends import LizardPermissionBackend
from rest_framework import generics, mixins
from rest_framework.renderers import BrowsableAPIRenderer, JSONRenderer
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView


COLNAME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'


class Root(APIView):
    def get(self, request, format=None):
        response = {
            'datasets': reverse('dataset-list', request=request),
            'locationgroups': reverse('locationgroup-list', request=request),
            'locations': reverse('location-list', request=request),
            'timeseries': reverse('timeseries-list', request=request),
        }
        user = getattr(request, 'user', None)
        if user is not None and user.is_superuser:
            response.update({
                'users': reverse('user-list', request=request),
                'groups': reverse('usergroup-list', request=request),
                'roles': reverse('role-list', request=request),
            })
        return Response(response)


class APIBaseView(object):
    renderer_classes = (JSONRenderer, BrowsableAPIRenderer)

    def _dispatch(self, handler, request, *args, **kwargs):
        try:
            return handler(request, *args, **kwargs)
        except Exception as ex:
            raise APIException(ex)


class APIReadOnlyListView(APIBaseView,
                  mixins.ListModelMixin,
                  generics.MultipleObjectAPIView):
    def get(self, request, *args, **kwargs):
        return self._dispatch(self._list, request, *args, **kwargs)

    def _list(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class APIListView(APIReadOnlyListView, mixins.CreateModelMixin):
    def post(self, request, *args, **kwargs):
        return self._dispatch(self._create, request, *args, **kwargs)

    @method_decorator(permission_required('add', raise_exception=True))
    def _create(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)


class APIProtectedListView(APIListView):
    @method_decorator(permission_required('staff', raise_exception=True))
    def _list(self, request, *args, **kwargs):
        return super(APIListView, self).list(request, *args, **kwargs)


class APIDetailView(APIBaseView,
                    mixins.RetrieveModelMixin,
                    mixins.UpdateModelMixin,
                    mixins.DestroyModelMixin,
                    generics.SingleObjectAPIView):
    def get(self, request, *args, **kwargs):
        return self._dispatch(self._retrieve, request, *args, **kwargs)

    def _retrieve(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        return self._dispatch(self._update, request, *args, **kwargs)

    @method_decorator(permission_required('change', raise_exception=True))
    def _update(self, request, *args, **kwargs):
        return self.retrieve(update, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        return self._dispatch(self._destroy, request, *args, **kwargs)

    @method_decorator(permission_required('delete', raise_exception=True))
    def _destroy(self, request, *args, **kwargs):
        return self.destroy(request, *args, **kwargs)


class APIProtectedDetailView(APIDetailView):
    @method_decorator(permission_required('staff', raise_exception=True))
    def _retrieve(self, request, *args, **kwargs):
        return super(APIDetailView, self).retrieve(request, *args, **kwargs)


class UserList(APIProtectedListView):
    model = User
    serializer_class = serializers.UserListSerializer


class UserDetail(APIProtectedDetailView):
    model = User
    serializer_class = serializers.UserDetailSerializer


class GroupList(APIProtectedListView):
    model = UserGroup
    serializer_class = serializers.GroupListSerializer


class GroupDetail(APIProtectedDetailView):
    model = UserGroup
    serializer_class = serializers.GroupDetailSerializer


class RoleList(APIProtectedListView):
    model = Role
    serializer_class = serializers.RoleListSerializer


class RoleDetail(APIProtectedDetailView):
    model = Role
    serializer_class = serializers.RoleDetailSerializer


class DataSetList(APIListView):
    model = DataSet
    serializer_class = serializers.DataSetListSerializer


class DataSetDetail(APIDetailView):
    model = DataSet
    serializer_class = serializers.DataSetDetailSerializer


class LocationGroupList(APIListView):
    model = LocationGroup
    serializer_class = serializers.LocationGroupListSerializer


class LocationGroupDetail(APIDetailView):
    model = LocationGroup
    serializer_class = serializers.LocationGroupDetailSerializer
    slug_field = 'code'
    slug_url_kwarg = 'code'


class LocationList(APIListView):
    model = Location
    serializer_class = serializers.LocationListSerializer


class LocationDetail(APIDetailView):
    model = Location
    serializer_class = serializers.LocationDetailSerializer
    slug_field = 'code'
    slug_url_kwarg = 'code'


class TimeseriesList(APIListView):
    model = Timeseries
    serializer_class = serializers.TimeseriesListSerializer


class TimeseriesDetail(APIDetailView):
    model = Timeseries
    serializer_class = serializers.TimeseriesDetailSerializer
    slug_field = 'code'
    slug_url_kwarg = 'code'


class EventList(APIReadOnlyListView):
    def list(self, request, code=None, format=None):
        result = Timeseries.objects.filter(code=code)
        if len(result) == 0:
            raise Http404("Geen timeseries gevonden die voldoen aan de query")
        ts = result[0]
        start = self.request.QUERY_PARAMS.get('start', None)
        end = self.request.QUERY_PARAMS.get('end', None)
        filter = self.request.QUERY_PARAMS.get('filter', None)
        if start is not None:
            start = datetime.strptime(start, COLNAME_FORMAT)
        if end is not None:
            end = datetime.strptime(end, COLNAME_FORMAT)
        df = ts.get_events(start=start, end=end, filter=filter)
        events = [
            dict([('datetime', timestamp.strftime(COLNAME_FORMAT))] + [
                (colname, row[i])
                for i, colname in enumerate(df.columns)
            ])
            for timestamp, row in df.iterrows()
        ]
        return Response(events)
