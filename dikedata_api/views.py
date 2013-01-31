# (c) Nelen & Schuurmans.  MIT licensed, see LICENSE.rst.
from __future__ import unicode_literals

from datetime import datetime

from django.conf import settings
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.models import User, Group as Role
from django.http import Http404
from django.utils.decorators import method_decorator

from rest_framework import generics, mixins
from rest_framework.renderers import BrowsableAPIRenderer, JSONRenderer
from rest_framework.response import Response

from lizard_security.models import DataSet, DataOwner, UserGroup

from ddsc_core.models import Location, Timeseries, Parameter

from dikedata_api import serializers
from dikedata_api.exceptions import APIException

COLNAME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
REST_FRAMEWORK = getattr(settings, 'REST_FRAMEWORK', {})
PAGINATE_BY = getattr(REST_FRAMEWORK, 'PAGINATE_BY', None)
PAGINATE_BY_PARAM = getattr(REST_FRAMEWORK, 'PAGINATE_BY_PARAM', None)


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
        return self.retrieve(self.request, *args, **kwargs)

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


class DataOwnerList(APIListView):
    model = DataOwner
    serializer_class = serializers.DataSetListSerializer


class DataOwnerDetail(APIDetailView):
    model = DataOwner
    serializer_class = serializers.DataSetDetailSerializer


class LocationList(APIListView):
    model = Location
    serializer_class = serializers.LocationListSerializer


class LocationDetail(APIDetailView):
    model = Location
    serializer_class = serializers.LocationDetailSerializer
    slug_field = 'uuid'
    slug_url_kwarg = 'uuid'


class TimeseriesList(APIListView):
    model = Timeseries
    serializer_class = serializers.TimeseriesListSerializer


class TimeseriesDetail(APIDetailView):
    model = Timeseries
    serializer_class = serializers.TimeseriesDetailSerializer
    slug_field = 'uuid'
    slug_url_kwarg = 'uuid'


class EventList(APIReadOnlyListView):
    def list(self, request, uuid=None, format=None):
        result = Timeseries.objects.filter(uuid=uuid)
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


class ParameterList(APIListView):
    model = Parameter
    serializer_class = serializers.ParameterListSerializer


class ParameterDetail(APIDetailView):
    model = Parameter
    serializer_class = serializers.ParameterDetailSerializer
