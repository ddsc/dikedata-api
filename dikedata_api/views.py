# (c) Nelen & Schuurmans.  MIT licensed, see LICENSE.rst.
from __future__ import unicode_literals

from datetime import datetime
import calendar
import logging
import mimetypes

from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.models import User, Group as Role
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpResponse
from django.utils.decorators import method_decorator

from rest_framework import generics
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView

import numpy as np

from tls import TLSRequestMiddleware

from lizard_security.models import DataSet, DataOwner, UserGroup

from ddsc_core.auth import PERMISSION_CHANGE
from ddsc_core.models import Location, Timeseries, Parameter, LogicalGroup

from dikedata_api import mixins, serializers
from dikedata_api.douglas_peucker import decimate, decimate_2d, decimate_until

from tslib.readers import ListReader

logger = logging.getLogger(__name__)

COLNAME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
COLNAME_FORMAT_MS = '%Y-%m-%dT%H:%M:%S.%fZ' # supports milliseconds
FILENAME_FORMAT = '%Y-%m-%dT%H.%M.%SZ'

mimetypes.init()


def write_events(user, data):
    if user is None:
        raise PermissionDenied("User not logged in.")
    reader = ListReader(data)
    series = {}
    permission = True
    for (uuid, df) in reader.get_series():
        ts = Timeseries.objects.get(uuid=uuid)
        series[uuid] = (ts, df)
        if not user.has_perm(PERMISSION_CHANGE, ts):
            permission = False
    if not permission:
        raise PermissionDenied("Permission denied")
    for uuid, (ts, df) in series.items():
        ts.set_events(df)
        ts.save()


def authenticate_request(request):
    # Sensors can authenticate by username and password in each request.
    # When they do, a login is faked and the request stream is overloaded,
    # forcing a re-parse of the event json data.

    if not isinstance(request.META, dict):
        return

    username = request.META.get('HTTP_USERNAME', None)
    password = request.META.get('HTTP_PASSWORD', None)

    if username and password:
        request.user = authenticate(username=username, password=password)
        if not request.user:
            raise PermissionDenied("Incorrect username/password.")
        if not hasattr(request, 'user_group_ids'):
            request.user_group_ids = set()
        if not request.user.is_anonymous():
            groups = request.user.user_group_memberships.values_list(
                'id', flat=True)
            request.user_group_ids = request.user_group_ids.union(groups)
        mw = TLSRequestMiddleware()
        mw.process_request(request)


class APIReadOnlyListView(mixins.BaseMixin, mixins.GetListModelMixin,
                          generics.MultipleObjectAPIView):
    pass


class APIListView(mixins.PostListModelMixin, APIReadOnlyListView):
    pass


class APIDetailView(mixins.BaseMixin, mixins.DetailModelMixin,
                    generics.SingleObjectAPIView):
    pass


class UserList(mixins.ProtectedListModelMixin, APIReadOnlyListView):
    model = User
    serializer_class = serializers.UserListSerializer


class UserDetail(mixins.ProtectedDetailModelMixin, APIDetailView):
    model = User
    serializer_class = serializers.UserDetailSerializer


class GroupList(mixins.ProtectedListModelMixin, APIReadOnlyListView):
    model = UserGroup
    serializer_class = serializers.GroupListSerializer


class GroupDetail(mixins.ProtectedDetailModelMixin, APIDetailView):
    model = UserGroup
    serializer_class = serializers.GroupDetailSerializer


class RoleList(mixins.ProtectedListModelMixin, APIReadOnlyListView):
    model = Role
    serializer_class = serializers.RoleListSerializer


class RoleDetail(mixins.ProtectedDetailModelMixin, APIDetailView):
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


class MultiEventList(mixins.BaseMixin, mixins.PostListModelMixin, APIView):

    def post(self, request, uuid=None):
        authenticate_request(request)

        serializer = serializers.MultiEventListSerializer(data=request.DATA)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        result = write_events(getattr(request, 'user', None), serializer.data)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=201, headers=headers)


class EventList(mixins.BaseMixin, mixins.PostListModelMixin, APIView):

    def post(self, request, uuid=None):
        authenticate_request(request)

        ts = Timeseries.objects.get(uuid=uuid)
        if ts.is_file():
            if not isinstance(request.META, dict):
                raise ValidationError("Missing request header")
            dt = request.META.get('HTTP_DATETIME', None)
            if not dt:
                raise ValidationError("Missing request header param")
            timestamp = datetime.strptime(dt, COLNAME_FORMAT)
            ts.set_file(timestamp, request.FILES)
            data = {'datetime' : dt, 'value' : reverse('event-detail',
                args=[uuid, dt], request=request)}
            ts.save()
            headers = self.get_success_headers(data)
            return Response(data, status=201, headers=headers)

        serializer = serializers.EventListSerializer(data=request.DATA)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        data = [{"uuid": uuid, "events": serializer.data}]
        result = write_events(getattr(request, 'user', None), data)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=201, headers=headers)

    def get(self, request, uuid=None, format=None):
        ts = Timeseries.objects.get(uuid=uuid)

        # grab GET parameters
        start = self.request.QUERY_PARAMS.get('start', None)
        end = self.request.QUERY_PARAMS.get('end', None)
        filter = self.request.QUERY_PARAMS.get('filter', None)
        eventsformat = self.request.QUERY_PARAMS.get('eventsformat', None)

        # parse start and end date
        if start is not None:
            try:
                start = datetime.strptime(start, COLNAME_FORMAT)
            except ValueError:
                # use the alternative format
                start = datetime.strptime(start, COLNAME_FORMAT_MS)
        if end is not None:
            try:
                end = datetime.strptime(end, COLNAME_FORMAT)
            except ValueError:
                # use the alternative format
                end = datetime.strptime(end, COLNAME_FORMAT_MS)

        # only return in jQuery Flot compatible format when requested
        if eventsformat is None:
            df = ts.get_events(start=start, end=end, filter=filter)
            response = self.format_default(request, ts, df)
        elif eventsformat == 'flot':
            df = ts.get_events(start=start, end=end, filter=filter)
            response = self.format_flot(request, ts, df, start, end)

        return Response(response)

    @staticmethod
    def format_default(request, ts, df):
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
        return events

    @staticmethod
    def format_flot(request, ts, df, start=None, end=None):
        tolerance = request.QUERY_PARAMS.get('tolerance', None)
        width = request.QUERY_PARAMS.get('width', None)
        height = request.QUERY_PARAMS.get('height', None)

        if len(df) > 0:
            def to_js_timestamp(dt):
                return float(calendar.timegm(dt.timetuple()) * 1000)
            # Add values to the response.
            # Convert event dates to timestamps with milliseconds since epoch.
            # TODO see if source timezone / display timezone are relevant
            timestamps = [to_js_timestamp(dt) for dt in df.index]

            # Decimate only operates on Numpy arrays, so convert our timestamps
            # back to one.
            timestamps = np.array(timestamps)
            values = df['value'].values

            # Decimate values (a.k.a. line simplification), using Ramer-Douglas-Peucker.
            # Determine tolerance using either the provided value,
            # or calculate it using width and height of the graph.
            if tolerance is not None:
                try:
                    tolerance = float(tolerance)
                except ValueError:
                    tolerance = None
            elif width is not None and height is not None:
                # Assume graph scales with min and max of the entire range here.
                # Otherwise we need to pass axes min/max as well.
                try:
                    width = float(width)
                    if start and end:
                        # use min and max of the actual requested graph range
                        tolerance_w_requested = (to_js_timestamp(end) - to_js_timestamp(start)) / width
                    else:
                        tolerance_w_requested = 0
                    # Check with min and max of the entire timeseries, and use
                    # whichever is higher.
                    # Timestamps are sorted, so we can just do this.
                    tolerance_w_possible = (timestamps[-1] - timestamps[0]) / width
                    tolerance_w = max(tolerance_w_requested, tolerance_w_possible)
                except ValueError:
                    tolerance_w = None

                try:
                    height = float(height)
                    tolerance_h = (values.max() - values.min()) / height
                except ValueError:
                    tolerance_h = None

                # Just use vertical tolerance for now, until we have a better 2D solution.
                tolerance = tolerance_h

            # Apply the actual line simplification.
            # Only possible on 2 or more values.
            if tolerance is not None and len(df) > 1:
                before = len(values)
                timestamps, values = decimate_until(timestamps, values, tolerance)
                logger.debug('decimate: %s values left of %s, with tol = %s', len(values), before, tolerance)

            data = zip(timestamps, values)
            xmin = timestamps[-1] # timestamps is sorted
            xmax = timestamps[0]  # timestamps is sorted
        else:
            # No events, nothing to return.
            data = []
            xmin = None
            xmax = None

        line = {
            'label': str(ts),
            'data': data,
            # These are added to determine the axis which will be related
            # to the graph line.
            'parameter_name': str(ts.parameter),
            'parameter_pk': ts.parameter.pk,
            # These are used to reset the graph boundaries when the first
            # line is plotted.
            'xmin': xmin,
            'xmax': xmax,
        }

        return line


class EventDetail(mixins.BaseMixin, APIView):
    def get(self, request, uuid=None, dt=None, format=None):
        ts = Timeseries.objects.get(uuid=uuid)
        timestamp = datetime.strptime(dt, FILENAME_FORMAT)
        (file_data, file_mime, file_size) = ts.get_file(timestamp)
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


class ParameterList(APIReadOnlyListView):
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
