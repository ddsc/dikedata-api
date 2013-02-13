# (c) Nelen & Schuurmans.  MIT licensed, see LICENSE.rst.
from __future__ import unicode_literals

from datetime import datetime

import mimetypes

from django.conf import settings
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.models import User, Group as Role
from django.http import Http404, HttpResponse
from django.utils.decorators import method_decorator

from rest_framework import generics, mixins
from rest_framework.renderers import BrowsableAPIRenderer, JSONRenderer
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView

from lizard_security.models import DataSet, DataOwner, UserGroup

from ddsc_core.models import Location, Timeseries, Parameter, LogicalGroup

from dikedata_api import serializers
from dikedata_api.exceptions import APIException

COLNAME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
FILENAME_FORMAT = '%Y-%m-%dT%H.%M.%SZ'

mimetypes.init()


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

    def get_queryset(self):
        kwargs = {'depth': 1}
        parameter = self.request.QUERY_PARAMS.get('parameter', None)
        if parameter:
            kwargs['timeseries__parameter__in'] = parameter.split(',')
        logicalgroup = self.request.QUERY_PARAMS.get('logicalgroup', None)
        if logicalgroup:
            kwargs['timeseries__logical_groups__in'] = logicalgroup.split(',')
        return Location.objects.filter(**kwargs).distinct()


class LocationDetail(APIDetailView):
    model = Location
    serializer_class = serializers.LocationDetailSerializer
    slug_field = 'uuid'
    slug_url_kwarg = 'uuid'


class TimeseriesList(APIListView):
    model = Timeseries
    serializer_class = serializers.TimeseriesListSerializer

    def get_queryset(self):
        kwargs = {}
        logicalgroup = self.request.QUERY_PARAMS.get('logicalgroup', None)
        if logicalgroup:
            kwargs['logical_groups__in'] = logicalgroup.split(',')
        location = self.request.QUERY_PARAMS.get('location', None)
        if location:
            kwargs['location__uuid__in'] = location.split(',')
        parameter = self.request.QUERY_PARAMS.get('parameter', None)
        if parameter:
            kwargs['parameter__in'] = parameter.split(',')
        return Timeseries.objects.filter(**kwargs).distinct()


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
        if ts.is_file():
            events = [
                dict([('datetime', timestamp.strftime(COLNAME_FORMAT)),
                    ('value', reverse('event-detail',
                    args=[ts.uuid, timestamp.strftime(FILENAME_FORMAT)],
                    request=request))])
                for timestamp, row in df.iterrows()
            ]
        else:
            events = [
                dict([('datetime', timestamp.strftime(COLNAME_FORMAT))] +
                    [(colname, row[i]) for i, colname in enumerate(df.columns)]
                )
                for timestamp, row in df.iterrows()
            ]
        return Response(events)


class EventDetail(APIView):
    def get(self, request, uuid=None, dt=None, format=None):
        result = Timeseries.objects.filter(uuid=uuid)
        if len(result) == 0:
            raise Http404("Geen timeseries gevonden die voldoen aan de query")
        ts = result[0]
        timestamp = datetime.strptime(dt, FILENAME_FORMAT)
        try:
            (file_data, file_mime, file_size) = ts.get_file(timestamp)
        except IOError:
            raise Http404("File not found")
        response = HttpResponse(file_data, mimetype=file_mime)
        if file_mime is not None:
            response['Content-Type'] = file_mime
        if (ts.value_type == Timeseries.ValueType.FILE):
            file_ext = mimetypes.guess_extension(file_mime)
            file_name = "%s-%s%s" % (ts.uuid, dt, file_ext)
            response['Content-Disposition'] = 'attachment; filename=' + file_name
        if (file_size > 0):
            response['Content-Length'] = file_size
        return response


class ParameterList(APIListView):
    model = Parameter
    serializer_class = serializers.ParameterListSerializer

    def get_queryset(self):
        kwargs = {'group' : 'Grootheid'}
        logicalgroup = self.request.QUERY_PARAMS.get('logicalgroup', None)
        if logicalgroup:
            kwargs['timeseries__logical_groups__in'] = logicalgroup.split(',')
        location = self.request.QUERY_PARAMS.get('location', None)
        if location:
            kwargs['timeseries__location__uuid__in'] = location.split(',')
        return Parameter.objects.filter(**kwargs).distinct()


class ParameterDetail(APIDetailView):
    model = Parameter
    serializer_class = serializers.ParameterDetailSerializer


class LogicalGroupList(APIListView):
    model = LogicalGroup
    serializer_class = serializers.LogicalGroupListSerializer

    def get_queryset(self):
        kwargs = {}
        location = self.request.QUERY_PARAMS.get('location', None)
        if location:
            kwargs['timeseries__location__uuid__in'] = location.split(',')
        parameter = self.request.QUERY_PARAMS.get('parameter', None)
        if parameter:
            kwargs['timeseries__parameter__in'] = parameter.split(',')
        return LogicalGroup.objects.filter(**kwargs).distinct()


class LogicalGroupDetail(APIDetailView):
    model = LogicalGroup
    serializer_class = serializers.LogicalGroupDetailSerializer
