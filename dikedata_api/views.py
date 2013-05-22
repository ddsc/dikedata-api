# (c) Nelen & Schuurmans.  MIT licensed, see LICENSE.rst.
from __future__ import unicode_literals

from datetime import datetime
import calendar
import logging
import mimetypes
import time
import json

from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.models import User, Group as Role
from django.core.exceptions import ValidationError
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import F, Sum
from django.http import Http404, HttpResponse
from django.utils.decorators import method_decorator
from django.db.models import Q

from rest_framework import exceptions as ex, generics
from rest_framework.parsers import JSONParser, FormParser
from rest_framework.renderers import JSONRenderer, BrowsableAPIRenderer
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView
from rest_framework.pagination import PaginationSerializer
from rest_framework.exceptions import ParseError
from rest_framework import status
from rest_framework.request import clone_request

import numpy as np

from tls import TLSRequestMiddleware

from lizard_security.models import DataSet, DataOwner, UserGroup, PermissionMapper

from ddsc_core.auth import PERMISSION_CHANGE
from ddsc_core.models import (Alarm, Alarm_Active, Alarm_Item, IdMapping,
                              Location, LogicalGroup, LogicalGroupEdge, Source,
                              Timeseries, Manufacturer, StatusCache)
from ddsc_core.models.aquo import Compartment
from ddsc_core.models.aquo import MeasuringDevice
from ddsc_core.models.aquo import MeasuringMethod
from ddsc_core.models.aquo import Parameter
from ddsc_core.models.aquo import ProcessingMethod
from ddsc_core.models.aquo import ReferenceFrame
from ddsc_core.models.aquo import Unit

from dikedata_api import mixins, serializers
from dikedata_api.parsers import CSVParser
from dikedata_api.douglas_peucker import decimate, decimate_2d, decimate_until
from dikedata_api.renderers import CSVRenderer

from tslib.readers import ListReader

logger = logging.getLogger(__name__)

COLNAME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
COLNAME_FORMAT_MS = '%Y-%m-%dT%H:%M:%S.%fZ' # supports milliseconds
FILENAME_FORMAT = '%Y-%m-%dT%H.%M.%S.%fZ'

mimetypes.init()



BOOL_LOOKUPS = ("isnull",)
INT_LOOKUPS = ("year", "month", "day", "week_day",)
STR_LOOKUPS = ("contains", "icontains", "startswith", "istartswith", "endswith", "iendswith", "search", "regex", "iregex",)
ALL_LOOKUPS = BOOL_LOOKUPS + INT_LOOKUPS + STR_LOOKUPS + ("exact", "iexact", "gt", "gte", "lt", "lte",)


class InvalidKey(ParseError):
    def __init__(self, key):
        message = "Unknown field or lookup: %s." % key
        super(ParseError, self).__init__(message)


def customfilter(view, qs, filter_json=None, order_field=None):
    """
    Function for adding filters to queryset.
    set 'customfilter_fields for allowed fields'
    :param view:                view (self)
    :param qs:                  queryset
    :param filter_json:         raw_json of filter key. example is '{"name__contains": "bla", "uuid__startswith": "7"}'
    :return:
    """
    filter_fields = {}
    if not view.customfilter_fields == '*':
        for item in view.customfilter_fields:
            if type(item) == tuple:
                filter_fields[item[0]] = item[1]
            else:
                filter_fields[item] = item

    exclude = False

    if filter_json:
        filter_dict = json.loads(filter_json)
    else:
        filter_dict = {}

    for key, value in filter_dict.items():
        #support for points in stead of double underscores
        key = key.replace('.', '__')
        #get key and lookup
        possible_lookup = key.rsplit('__',1)
        if len(possible_lookup) == 2 and possible_lookup[1] in ALL_LOOKUPS:
            key = possible_lookup[0]
            lookup = possible_lookup[1]
        else:
            lookup = 'exact'

        #check on include or exclude
        if key.startswith('-'):
            exclude = True
            key = key.lstrip('-')

        #check if key is allowed
        if key in filter_fields.keys():
            key = filter_fields[key]

        if value:
            if exclude:
                qs = qs.exclude(**{'%s__%s' % (key, lookup): value})
            else:
                qs = qs.filter(**{'%s__%s' % (key, lookup): value})

    if order_field:
        order_field = order_field.replace('.','__')
        if order_field in filter_fields:
            order_field = filter_fields[order_field]
        qs = qs.order_by(order_field)

    return qs


def write_events(user, data):
    if user is None:
        raise ex.NotAuthenticated("User not logged in.")
    reader = ListReader(data)
    permission = True
    locations = {}
    series = {}
    events = []
    total = 0
    for (uuid, df) in reader.get_series():
        if uuid not in series:
            try:
                series[uuid] = Timeseries.objects.get(uuid=uuid)
            except Timeseries.DoesNotExist:
                map = IdMapping.objects.get(user__username=user, remote_id=uuid)
                series[uuid] = map.timeseries
            locations[series[uuid].location_id] = 1
        events.append((uuid, df))
        if not user.has_perm(PERMISSION_CHANGE, series[uuid]):
            permission = False
    if not permission:
        raise ex.PermissionDenied("Permission denied")
    for (uuid, df) in events:
        series[uuid].set_events(df)
        total += len(df)
        series[uuid].save()
    return total, len(series), len(locations)


def sanitize_filename(fn):
    '''strips characters not allowed in a filename'''
    # illegal characters in Windows and Linux filenames, such as slashes
    filename_badchars = "<>:\"/\\|?*\0"
    # build character translation table
    filename_badchars_table = {ord(char): None for char in filename_badchars}

    if isinstance(fn, unicode): # TODO remove for python 3
        # strip characters like ":"
        fn = fn.translate(filename_badchars_table)
        # remove trailing space or period, which are not allowed in Windows
        fn = fn.rstrip(". ")
    else:
        raise Exception("only unicode strings are supported")
    return fn


class APIReadOnlyListView(mixins.BaseMixin, mixins.GetListModelMixin,
                          generics.MultipleObjectAPIView):

    customfilter_fields = '*'
    select_related = None

    def get_queryset(self):
        qs = self.model.objects
        filter = self.request.QUERY_PARAMS.get('filter', None)
        order = self.request.QUERY_PARAMS.get('order', None)
        if filter or order:
            qs = customfilter(self, qs, filter, order)

        if self.select_related:
            qs = qs.select_related(*self.select_related)

        return qs.distinct()


class APIListView(mixins.PostListModelMixin, APIReadOnlyListView):
    pass


class APIDetailView(mixins.BaseMixin, mixins.DetailModelMixin,
                    generics.SingleObjectAPIView):

    select_related = None

    def get_queryset(self):
        qs = self.model.objects

        if self.select_related:
            qs = qs.select_related(*self.select_related)
        return qs


class Aquo(APIReadOnlyListView):
    #model = Parameter
    #serializer_class = serializers.Aqu
    customfilter_fields = ('id', 'code', 'description', 'visible')


class Parameter(Aquo):
    model = Parameter
    serializer_class = serializers.ParameterSerializer
    customfilter_fields = ('id', 'code', 'description', 'group', 'visible')


class Compartment(Aquo):
    model = Compartment
    serializer_class = serializers.CompartmentSerializer


class MeasuringDevice(Aquo):
    model = MeasuringDevice
    serializer_class = serializers.MeasuringDeviceSerializer


class MeasuringMethod(Aquo):
    model = MeasuringMethod
    serializer_class = serializers.MeasuringMethodSerializer


class ProcessingMethod(Aquo):
    model = ProcessingMethod
    serializer_class = serializers.ProcessingMethodSerializer


class ReferenceFrame(Aquo):
    model = ReferenceFrame
    serializer_class = serializers.ReferenceFrameSerializer


class Unit(Aquo):
    model = Unit
    serializer_class = serializers.UnitSerializer


class ManufacturerList(APIListView):
    model = Manufacturer
    serializer_class = serializers.ManufacturerSerializer
    customfilter_fields = ['code', 'name']


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
    select_related = ['owner']

    def get_queryset(self):
        qs = super(DataSetList, self).get_queryset()

        if not self.request.user.is_authenticated():
            qs = self.model.objects.none()
        elif self.request.user.is_superuser:
            qs = qs
        elif self.request.QUERY_PARAMS.get('management', False):
            qs = qs.filter(owner__data_managers=self.request.user)
        else:
            qs = qs.filter(permission_mappers__user_group__members=self.request.user)
        return qs


class DataSetDetail(APIDetailView):
    model = DataSet
    serializer_class = serializers.DataSetDetailSerializer
    select_related = ['owner']


class DataOwnerList(APIListView):
    model = DataOwner
    serializer_class = serializers.DataOwnerListSerializer

    def get_queryset(self):
        qs = super(DataOwnerList, self).get_queryset()

        if not self.request.user.is_authenticated():
            qs = self.model.objects.none()
        elif self.request.user.is_superuser:
            qs = qs
        elif self.request.QUERY_PARAMS.get('management', False):
            qs = qs.filter(data_managers=self.request.user)
        else:
            qs.filter(dataset__in=DataSet.objects.filter(permission_mappers__user_group__members=self.request.user).distinct())

        return qs.distinct()


class DataOwnerDetail(APIDetailView):
    model = DataOwner
    serializer_class = serializers.DataOwnerDetailSerializer


    def get_queryset(self):
        qs = super(DataOwnerDetail, self).get_queryset()

        if not self.request.user.is_authenticated():
            qs = self.model.objects.none()

        return qs.distinct()


class LocationList(APIListView):
    model = Location
    serializer_class = serializers.LocationListSerializer

    customfilter_fields = ('id', 'uuid', 'name', ('owner', 'owner__name'), 'point_geometry', 'show_on_map')

    def get_queryset(self):
        qs = super(LocationList, self).get_queryset()

        if not self.request.user.is_authenticated():
            qs = self.model.objects.filter(timeseries__owner=None)
        elif self.request.user.is_superuser:
            qs = qs
        elif self.request.QUERY_PARAMS.get('management', False):
            qs = qs.filter(Q(owner__data_managers=self.request.user)|Q(owner=None))
        else:
            qs = qs.filter(timeseries__data_set__in=DataSet.objects.filter(permission_mappers__user_group__members=self.request.user).distinct())

        #special filters
        kwargs = {}
        parameter = self.request.QUERY_PARAMS.get('parameter', None)
        if parameter:
            kwargs['timeseries__parameter__in'] = parameter.split(',')
        logicalgroup = self.request.QUERY_PARAMS.get('logicalgroup', None)
        if logicalgroup:
            kwargs['timeseries__logical_groups__in'] = logicalgroup.split(',')
        has_geometry = self.request.QUERY_PARAMS.get('has_geometry', None)
        if has_geometry == 'true':
            kwargs['point_geometry__isnull'] = False
        for_map = self.request.QUERY_PARAMS.get('for_map', None)
        if for_map == 'true':
            kwargs['show_on_map'] = True
        return qs.filter(**kwargs).distinct()


class LocationDetail(APIDetailView):
    model = Location
    serializer_class = serializers.LocationDetailSerializer
    slug_field = 'uuid'
    slug_url_kwarg = 'uuid'

    def get_queryset(self):
        qs = super(LocationDetail, self).get_queryset()

        if not self.request.user.is_authenticated():
            qs = self.model.objects.filter(timeseries__owner=None)
        elif self.request.user.is_superuser:
            qs = qs
        else:
            qs = qs.filter(Q(timeseries__data_set__in=DataSet.objects.filter(permission_mappers__user_group__members=self.request.user).distinct())|
                            Q(owner__data_managers=self.request.user)|Q(owner=None))
        return qs.distinct()



class TimeseriesList(APIListView):
    model = Timeseries
    serializer_class = serializers.TimeseriesListSerializer

    customfilter_fields = ('id', 'uuid', 'name', 'location__name', ('parameter', 'parameter__code'),
                           ('unit', 'unit__code'), ('owner', 'owner__name'), 'source')
    select_related = ['location', 'parameter', 'unit', 'owner', 'source']

    def get_queryset(self):
        qs = super(TimeseriesList, self).get_queryset()

        if not self.request.user.is_authenticated():
            qs = self.model.objects.none()
        elif self.request.user.is_superuser:
            qs = qs
        elif self.request.QUERY_PARAMS.get('management', False):
            qs = qs.filter(Q(owner__data_managers=self.request.user)|Q(owner=None))
            #    Q(data_set__permission_mappers__in=
            #         PermissionMapper.objects.filter(permission_group__permissions__codename='change_timeseries',
            #                                         user_group__members=self.request.user)
            #   ))
        else:
            qs = qs.filter(data_set__in=DataSet.objects.filter(permission_mappers__user_group__members=self.request.user))

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
        value_type = self.request.QUERY_PARAMS.get('value_type', None)
        if value_type:
            kwargs['value_type__in'] = value_type.split(',')
        name = self.request.QUERY_PARAMS.get('name', None)
        if name:
            kwargs['name__icontains'] = name
        return qs.filter(**kwargs).distinct()


class TimeseriesDetail(APIDetailView):
    model = Timeseries
    serializer_class = serializers.TimeseriesDetailSerializer
    slug_field = 'uuid'
    slug_url_kwarg = 'uuid'
    select_related = ['id', 'location', 'parameter', 'unit', 'source', 'owner', 'processing_method', 'measuring_method',
                      'measuring_device', 'compartment', 'reference_frame']

    def get_queryset(self):
        qs = super(TimeseriesDetail, self).get_queryset()

        if not self.request.user.is_authenticated():
            qs = self.model.objects.none()
        elif self.request.user.is_superuser:
            qs = qs
        else:
            qs = qs.filter(Q(data_set__in=DataSet.objects.filter(permission_mappers__user_group__members=self.request.user).distinct()) |
                           Q(owner__data_managers=self.request.user)|Q(owner=None))
        return qs.distinct()



class BaseEventView(mixins.BaseMixin, mixins.PostListModelMixin, APIView):
    pass


class MultiEventList(BaseEventView):
    parser_classes = JSONParser, FormParser, CSVParser

    def post(self, request, uuid=None):
        start = time.time()
        serializer = serializers.MultiEventListSerializer(data=request.DATA)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        e, t, l = write_events(getattr(request, 'user', None), serializer.data)
        headers = self.get_success_headers(serializer.data)
        elapsed = (time.time() - start) * 1000
        logger.info("POST: Wrote %d events for %d timeseries at %d locations " \
                    "in %d ms for user %s" %
                    (e, t, l, elapsed, getattr(request, 'user', None)))
        return Response(serializer.data, status=201, headers=headers)


class EventList(BaseEventView):
    renderer_classes = JSONRenderer, BrowsableAPIRenderer, CSVRenderer

    def post(self, request, uuid=None):
        start = time.time()
        ts = Timeseries.objects.get(uuid=uuid)
        if not request.user.has_perm(PERMISSION_CHANGE, ts):
            raise ex.PermissionDenied('No change permission on timeseries')
        if ts.is_file():
            if not isinstance(request.META, dict):
                raise ValidationError("Missing request header")
            dt = request.META.get('HTTP_DATETIME', None)
            if not dt:
                raise ValidationError("Missing request header param")
            try:
                timestamp = datetime.strptime(dt, COLNAME_FORMAT)
            except ValueError:
                # use the alternative format
                timestamp = datetime.strptime(dt, COLNAME_FORMAT_MS)
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
        e, t, l = write_events(getattr(request, 'user', None), data)
        headers = self.get_success_headers(serializer.data)
        elapsed = (time.time() - start) * 1000
        logger.info("POST: Wrote %d events for %d timeseries at %d locations " \
                    "in %d ms for user %s" %
                    (e, t, l, elapsed, getattr(request, 'user', None)))
        return Response(serializer.data, status=201, headers=headers)


    def get(self, request, uuid=None):
        ts = Timeseries.objects.get(uuid=uuid)
        headers = {}

        # grab GET parameters
        start = self.request.QUERY_PARAMS.get('start', None)
        end = self.request.QUERY_PARAMS.get('end', None)
        filter = self.request.QUERY_PARAMS.get('filter', None)
        format = self.request.QUERY_PARAMS.get('format', None)
        eventsformat = self.request.QUERY_PARAMS.get('eventsformat', None)
        page_num = self.request.QUERY_PARAMS.get('page', 1)
        combine_with = self.request.QUERY_PARAMS.get('combine_with', None)
        ignore_rejected = self.request.QUERY_PARAMS.get('ignore_rejected', None)

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

        if format == 'csv':
            # in case of csv return a dataframe and let the renderer handle it
            response = ts.get_events(start=start, end=end, filter=filter)
            headers['Content-Disposition'] = 'attachment; filename=%s-%s.csv' \
                % (uuid, sanitize_filename(ts.name))
        elif eventsformat is None:
            df = ts.get_events(start=start, end=end, filter=filter, ignore_rejected=ignore_rejected)
            all = self.format_default(request, ts, df)
            ps = generics.MultipleObjectAPIView(request=request)
            page_size = ps.get_paginate_by(None)
            if not page_size:
                return Response(all)
            paginator = Paginator(all, page_size)
            try:
                page = paginator.page(page_num)
            except PageNotAnInteger:
                page = paginator.page(1)
            except EmptyPage:
                page = paginator.page(paginator.num_pages)
            context = {'request':request}
            serializer = PaginationSerializer(instance=page, context=context)
            response = serializer.data
        elif eventsformat == 'flot' and combine_with is not None:
            # scatterplot, pad to hourly frequency
            other_ts = Timeseries.objects.get(uuid=combine_with)
            # returns an object ready for a jQuery scatter plot
            df_xaxis = ts.get_events(
                start=start,
                end=end,
                filter=filter,
                ignore_rejected=ignore_rejected).asfreq('1H', method='pad')
            df_yaxis = other_ts.get_events(
                start=start,
                end=end,
                filter=filter,
                ignore_rejected=ignore_rejected).asfreq('1H', method='pad')
            response = self.format_flot_scatter(request, df_xaxis, df_yaxis, ts, other_ts, start, end)
        elif eventsformat == 'flot':
            # only return in jQuery Flot compatible format when requested
            timer_start = datetime.now()
            df = ts.get_events(
                start=start,
                end=end,
                filter=filter,
                ignore_rejected=ignore_rejected)
            timer_get_events = datetime.now() - timer_start
            response = self.format_flot(request, ts, df, start, end, timer_get_events=timer_get_events)

        return Response(data=response, headers=headers)

    @staticmethod
    def format_default(request, ts, df):
        if ts.is_file():
            events = [
                dict([('datetime', timestamp.strftime(COLNAME_FORMAT_MS)),
                    ('value', reverse('event-detail',
                    args=[ts.uuid, timestamp.strftime(FILENAME_FORMAT)],
                    request=request))])
                for timestamp, row in df.iterrows()
            ]
        else:
            events = [
                dict([('datetime', timestamp.strftime(COLNAME_FORMAT_MS))] +
                    [(colname, row[i]) for i, colname in enumerate(df.columns)]
                )
                for timestamp, row in df.iterrows()
            ]
        return events

    @staticmethod
    def format_flot_scatter(request, df_xaxis, df_yaxis, ts, other_ts, start, end):
        if len(df_xaxis) > 0 and len(df_yaxis) > 0:
            data = zip(df_xaxis['value'].values, df_yaxis['value'].values)
        else:
            data = []
        line = {
            'label': '{} vs. {}'.format(ts, other_ts),
            'data': data,
            # These are added to determine the axis which will be related
            # to the graph line.
            'axis_label_x': '{}, {} ({})'.format(
                str(ts),
                str(ts.parameter),
                str(ts.unit)
            ),
            'axis_label_y': '{}, {} ({})'.format(
                str(other_ts),
                str(other_ts.parameter),
                str(other_ts.unit)
            ),
            # These are used to reset the graph boundaries when the first
            # line is plotted.
            'xmin': None,
            'xmax': None
        }

        return line

    @staticmethod
    def format_flot(request, ts, df, start=None, end=None, timer_get_events=None):
        tolerance = request.QUERY_PARAMS.get('tolerance', None)
        width = request.QUERY_PARAMS.get('width', None)
        height = request.QUERY_PARAMS.get('height', None)

        timer_to_js_timestamps = None
        timer_douglas_peucker = None
        timer_zip = None

        if len(df) > 0:
            def to_js_timestamp(dt):
                # Both are passed directly to Javascript's Date constructor.
                # Older browsers only support the first, but we can drop support for them.
                # So, just use the ISO 8601 format.
                return float(calendar.timegm(dt.timetuple()) * 1000)
                #return dt.strftime(COLNAME_FORMAT_MS)
            # Add values to the response.
            # Convert event dates to timestamps with milliseconds since epoch.
            # TODO see if source timezone / display timezone are relevant
            timer_start = datetime.now()
            timestamps = [to_js_timestamp(dt) for dt in df.index]

            # Decimate only operates on Numpy arrays, so convert our timestamps
            # back to one.
            timestamps = np.array(timestamps)
            timer_to_js_timestamps = datetime.now() - timer_start
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

                # Disable horizontal tolerance for now.
                '''
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
                '''

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
                timer_start = datetime.now()
                timestamps, values = decimate_until(timestamps, values, tolerance)
                timer_douglas_peucker = datetime.now() - timer_start
                logger.debug('decimate: %s values left of %s, with tol = %s', len(values), before, tolerance)

            timer_start = datetime.now()
            data = zip(timestamps, values)
            timer_zip = datetime.now() - timer_start
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
            'axis_label': '{} ({})'.format(str(ts.parameter), str(ts.unit)),
            'parameter_pk': ts.parameter.pk,
            # These are used to reset the graph boundaries when the first
            # line is plotted.
            'xmin': xmin,
            'xmax': xmax,
            'timer_get_events': str(timer_get_events),
            'timer_to_js_timestamps': str(timer_to_js_timestamps),
            'timer_douglas_peucker': str(timer_douglas_peucker),
            'timer_zip': str(timer_zip),
        }

        return line


class EventDetail(BaseEventView):

    def get(self, request, uuid=None, dt=None):
        ts = Timeseries.objects.get(uuid=uuid)
        if not ts.is_file():
            raise MethodNotAllowed(
                "Cannot GET single event detail of non-file timeseries.")
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


class SourceList(APIListView):
    model = Source
    serializer_class = serializers.SourceListSerializer
    customfilter_fields = ('id', 'uuid', 'name', ('manufacturer', 'manufacturer__name',), 'details', 'frequency', 'timeout')
    select_related = ['manufacturer']

    def get_queryset(self):
        qs = super(SourceList, self).get_queryset()

        if not self.request.user.is_authenticated():
            qs = self.model.objects.none()
        elif self.request.user.is_superuser:
            qs = qs
        elif self.request.QUERY_PARAMS.get('management', False):
            qs = qs.filter(Q(owner__data_managers=self.request.user)|Q(owner=None))
        else:
            qs = qs.filter(timeseries__data_set__in=DataSet.objects.filter(permission_mappers__user_group__members=self.request.user).distinct())

        return qs.distinct()


class SourceDetail(APIDetailView):
    model = Source
    serializer_class = serializers.SourceDetailSerializer
    slug_field = 'uuid'
    slug_url_kwarg = 'uuid'
    select_related = ['manufacturer']

    def get_queryset(self):
        qs = super(SourceDetail, self).get_queryset()

        if not self.request.user.is_authenticated():
            qs = self.model.objects.none()
        elif self.request.user.is_superuser:
            qs = qs
        else:
            qs = qs.filter(Q(timeseries__data_set__in=DataSet.objects.filter(permission_mappers__user_group__members=self.request.user).distinct())|
                            Q(owner__data_managers=self.request.user)|Q(owner=None))

        return qs.distinct()


class LogicalGroupList(APIListView):
    model = LogicalGroup
    serializer_class = serializers.LogicalGroupListSerializer
    select_related = ['owner', 'parents']

    def get_queryset(self):
        qs = super(LogicalGroupList, self).get_queryset()

        if not self.request.user.is_authenticated():
            qs = self.model.objects.none()
        elif self.request.user.is_superuser:
            qs = qs
        elif self.request.QUERY_PARAMS.get('management', False):
            qs = qs.filter(owner__data_managers=self.request.user)
        else:
            qs = qs.filter(owner__dataset__in=DataSet.objects.filter(permission_mappers__user_group__members=self.request.user).distinct())

        #special filters
        kwargs = {}
        location = self.request.QUERY_PARAMS.get('location', None)
        if location:
            kwargs['timeseries__location__uuid__in'] = location.split(',')
        parameter = self.request.QUERY_PARAMS.get('parameter', None)
        if parameter:
            kwargs['timeseries__parameter__in'] = parameter.split(',')
        return qs.filter(**kwargs).distinct()

    def post_save(self, obj, created=True):
        """
            custom function for saving many2manuy relation to self
            This save method is not transaction save and without validation on m2m parent relation.
            Django Restframework acts strange with 2 coonections to same model, so model instance is crated directly.
        """
        cur_parent_links = dict([(item.parent.id, item) for item in obj.parents.all()])
        req_parent_links = self.request.DATA.getlist('parents')

        for item in req_parent_links:
            item = json.loads(item)

            if item['parent'] in cur_parent_links and not self.request.method == 'POST':
                del cur_parent_links[item['parent']]

            elif 'parent' in item and item['parent'] is not None:
                #create item
                print 'create link'
                item['child'] = obj
                item['parent'] = LogicalGroup.objects.get(pk=item['parent'])
                parent_link = LogicalGroupEdge(**item)
                #todo: validation
                #errors = parent_link.errors
                parent_link.save()

        #delete the leftovers
        for item in cur_parent_links.values():
            item.delete()


class LogicalGroupDetail(APIDetailView):
    model = LogicalGroup
    serializer_class = serializers.LogicalGroupDetailSerializer
    select_related = ['owner', 'parents']

    def get_queryset(self):
        qs = super(LogicalGroupDetail, self).get_queryset()

        if not self.request.user.is_authenticated():
            qs = self.model.objects.none()
        elif self.request.user.is_superuser:
            qs = qs
        else:
            qs = qs.filter(Q(owner__dataset__in=DataSet.objects.filter(permission_mappers__user_group__members=self.request.user).distinct())|
                             Q(owner__data_managers=self.request.user))
        return qs.distinct()

    def post_save(self, obj, created=True):
        """
            custom function for saving many2manuy relation to self
            This save method is not transaction save and without validation on m2m parent relation.
            Django Restframework acts strange with 2 coonections to same model, so model instance is crated directly.
        """
        cur_parent_links = dict([(item.parent.id, item) for item in obj.parents.all()])

        req_parent_links = self.request.DATA.getlist('parents')

        for item in req_parent_links:
            item = json.loads(item)

            if item['parent'] in cur_parent_links and not self.request.method == 'POST':
                del cur_parent_links[item['parent']]

            elif 'parent' in item and item['parent'] is not None:
                #create item
                print 'create link'
                item['child'] = obj
                item['parent'] = LogicalGroup.objects.get(pk=item['parent'])
                parent_link = LogicalGroupEdge(**item)
                #todo: validation
                #errors = parent_link.errors
                parent_link.save()

        #delete the leftovers
        for item in cur_parent_links.values():
            item.delete()


class AlarmActiveList(APIListView):
    model = Alarm_Active
    serializer_class = serializers.Alarm_ActiveListSerializer
    select_related = ['alarm']

    def get_queryset(self):
        qs = super(AlarmActiveList, self).get_queryset()

        if not self.request.QUERY_PARAMS.get('all', False):
            #only return active alarms
            qs = qs.filter(active=True)

        if self.request.user.is_superuser:
            return qs
        else:
            return qs.filter(alarm__object_id=self.request.user.id).distinct()


class AlarmActiveDetail(APIDetailView):
    model = Alarm_Active
    serializer_class = serializers.Alarm_ActiveDetailSerializer
    select_related = ['alarm']

    def get_queryset(self):
        qs = super(AlarmActiveDetail, self).get_queryset()

        if self.request.user.is_superuser:
            return qs
        else:
            return qs.filter(alarm__object_id=self.request.user.id).distinct()


class AlarmSettingList(APIListView):
    model = Alarm
    serializer_class = serializers.AlarmSettingListSerializer

    def get_queryset(self):
        qs = super(AlarmSettingList, self).get_queryset()

        if not self.request.user.is_authenticated():
            return self.model.objects.none()
        elif self.request.user.is_superuser:
            return qs
        else:
            return qs.filter(object_id=self.request.user.id).distinct()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.DATA, files=request.FILES)

        if serializer.is_valid():
            if self.pre_save(serializer.object):
                self.object = serializer.save(force_insert=True)
                self.post_save(self.object, created=True)
                headers = self.get_success_headers(serializer.data)
                return Response(serializer.data, status=status.HTTP_201_CREATED,
                            headers=headers)
            else:
                return Response(self.errors, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def pre_save(self, obj):

        if obj.object_id is None:
            obj.content_object = self.request.user

        self.update_alarm_items = []
        self.create_alarm_items = []
        self.delete_alarm_items = []
        errors = []
        error = False

        cur_alarm_items = dict([(item.id, item) for item in obj.alarm_item_set.all()])

        req_alarm_items = self.request.DATA.getlist('alarm_item_set')

        for item in req_alarm_items:
            item = json.loads(item)
            if self.request.method == 'POST' or not 'id' in item or item['id'] is None:
                #create item
                item['alarm_id'] = obj.id
                alarm_item = serializers.AlarmItemDetailSerializer(None, data=item)

                if alarm_item.is_valid():
                    self.create_alarm_items.append(alarm_item)
                else:
                    errors.append(alarm_item.errors)
                    error = True

            elif item['id'] in cur_alarm_items:
                #update
                cur_item = cur_alarm_items[item['id']]
                alarm_item = serializers.AlarmItemDetailSerializer(cur_item, data=item)
                if alarm_item.is_valid():
                    self.update_alarm_items.append(alarm_item)
                else:
                    errors.append(alarm_item.errors)
                    error = True

                del cur_alarm_items[item['id']]

        #delete the leftovers
        for alarm_item in cur_alarm_items.values():
            self.delete_alarm_items.append(alarm_item)

        if error:
            self.errors = {'alarm_item_set': errors}
            return False
        else:
            return True

    def post_save(self, obj, created=True):
        """
            custom function for saving nested alarm items
            This save method is not transaction save and without validation on the alarm_items.
            Please refactor this function when write support is added to django rest framework
            (work in progress at this moment)
        """

        for item in self.update_alarm_items:
            item.save()

        for item in self.create_alarm_items:
            item.object.alarm = obj
            item.save()

        for item in self.delete_alarm_items:
            item.delete()



class AlarmSettingDetail(APIDetailView):
    model = Alarm
    serializer_class = serializers.AlarmSettingDetailSerializer
    select_related = ['alarm_item_set', 'alarm_item_set__alarm_type'] #todo: this doesn't work, find other way

    def get_queryset(self):
        qs = super(AlarmSettingDetail, self).get_queryset()

        if not self.request.user.is_authenticated():
            return self.model.objects.none()
        elif self.request.user.is_superuser:
            return qs
        else:
            return qs.filter(object_id=self.request.user.id).distinct()

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        self.object = None
        try:
            self.object = self.get_object()
        except Http404:
            # If this is a PUT-as-create operation, we need to ensure that
            # we have relevant permissions, as if this was a POST request.
            self.check_permissions(clone_request(request, 'POST'))
            created = True
            save_kwargs = {'force_insert': True}
            success_status_code = status.HTTP_201_CREATED
        else:
            created = False
            save_kwargs = {'force_update': True}
            success_status_code = status.HTTP_200_OK

        serializer = self.get_serializer(self.object, data=request.DATA,
                                         files=request.FILES, partial=partial)

        if serializer.is_valid():
            if self.pre_save(serializer.object):
                self.object = serializer.save(**save_kwargs)
                self.post_save(self.object, created=created)
                return Response(serializer.data, status=success_status_code)
            else:
                return Response(self.errors, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def pre_save(self, obj):

        if obj.object_id is None:
            obj.content_object = self.request.user

        self.update_alarm_items = []
        self.create_alarm_items = []
        self.delete_alarm_items = []
        errors = []
        error = False

        cur_alarm_items = dict([(item.id, item) for item in obj.alarm_item_set.all()])

        req_alarm_items = self.request.DATA.getlist('alarm_item_set')

        for item in req_alarm_items:
            item = json.loads(item)
            if self.request.method == 'POST' or not 'id' in item or item['id'] is None:
                #create item
                item['alarm_id'] = obj.id
                alarm_item = serializers.AlarmItemDetailSerializer(None, data=item)

                if alarm_item.is_valid():
                    self.create_alarm_items.append(alarm_item)
                else:
                    errors.append(alarm_item.errors)
                    error = True

            elif item['id'] in cur_alarm_items:
                #update
                cur_item = cur_alarm_items[item['id']]
                alarm_item = serializers.AlarmItemDetailSerializer(cur_item, data=item)
                if alarm_item.is_valid():
                    self.update_alarm_items.append(alarm_item)
                else:
                    errors.append(alarm_item.errors)
                    error = True

                del cur_alarm_items[item['id']]

        #delete the leftovers
        for alarm_item in cur_alarm_items.values():
            self.delete_alarm_items.append(alarm_item)


        if error:
            self.errors = {'alarm_item_set': errors}
            return False
        else:
            return True

    def post_save(self, obj, created=True):
        """
            custom function for saving nested alarm items
            This save method is not transaction save and without validation on the alarm_items.
            Please refactor this function when write support is added to django rest framework
            (work in progress at this moment)
        """

        for item in self.update_alarm_items:
            item.save()

        for item in self.create_alarm_items:
            item.object.alarm = obj
            item.save()

        for item in self.delete_alarm_items:
            item.delete()


class AlarmItemDetail(APIDetailView):
    model = Alarm_Item
    serializer_class = serializers.AlarmItemDetailSerializer


class StatusCacheList(APIListView):
    model = StatusCache
    serializer_class = serializers.StatusCacheListSerializer
    customfilter_fields = ('id', 'timeseries__name', ('timeseries__parameter', 'timeseries__parameter__code'),
                           'nr_of_measurements_total', 'nr_of_measurements_reliable', 'nr_of_measurements_doubtful',
                           'nr_of_measurements_unreliable', 'min_val', 'max_val', 'mean_val', 'std_val', 'status_date')
    select_related = ['timeseries', 'timeseries__parameter']

    def get_queryset(self):
        qs = super(StatusCacheList, self).get_queryset()

        if not self.request.user.is_authenticated():
            qs = self.model.objects.none()
        elif self.request.user.is_superuser:
            qs = qs
        else:
            qs = qs.filter(timeseries__data_set__in=DataSet.objects.filter(permission_mappers__user_group__members=self.request.user).distinct())

        return qs.distinct()


class StatusCacheDetail(APIDetailView):
    model = StatusCache
    serializer_class = serializers.StatusCacheDetailSerializer
    customfilter_fields = ('id', 'timeseries__name', ('timeseries__parameter', 'timeseries__parameter__code'),
                           'nr_of_measurements_total', 'nr_of_measurements_reliable', 'nr_of_measurements_doubtful',
                           'nr_of_measurements_unreliable', 'min_val', 'max_val', 'mean_val', 'std_val', 'status_date')
    select_related = ['timeseries', 'timeseries__parameter']

    def get_queryset(self):
        qs = super(StatusCacheDetail, self).get_queryset()

        if not self.request.user.is_authenticated():
            qs = self.model.objects.none()
        elif self.request.user.is_superuser:
            qs = qs
        else:
            qs = qs.filter(timeseries__data_set__in=DataSet.objects.filter(permission_mappers__user_group__members=self.request.user).distinct())
        return qs


class Summary(APIReadOnlyListView):
    def get(self, request, uuid=None):

        if not request.user.is_authenticated():
            total = 0
            disrupted_timeseries = 0
            active_alarms = 0
            new_events = 0
        else:
            ts_manager = Timeseries.objects
            aa_manager = Alarm_Active.objects
            sc_manager = StatusCache.objects

            if not request.user.is_superuser:
                ts_manager = ts_manager.filter(data_set__in=DataSet.objects.filter(permission_mappers__user_group__members=request.user))
                aa_manager = aa_manager.filter(alarm__object_id=request.user.id)
                sc_manager = sc_manager.filter(timeseries__data_set__in=DataSet.objects.filter(permission_mappers__user_group__members=request.user))

            total = ts_manager.count()
            disrupted_timeseries = ts_manager.values('source__frequency').extra(
                where=["latest_value_timestamp < now() - ddsc_core_source" \
                       ".frequency * INTERVAL '1 SECOND'"]).count()

            active_alarms = aa_manager.filter(active=True).count()
            status = sc_manager.values('date') \
                .annotate((Sum('nr_of_measurements_total'))) \
                .order_by('-date')[:1]
    
            if len(status) > 0 and 'nr_of_measurements_total__sum' in status[0]:
                new_events = status[0]['nr_of_measurements_total__sum']
            else:
                new_events = 0

        data = {
            'timeseries' : {
                'total' : total,
                'disrupted' : disrupted_timeseries,
            },
            'alarms' : {
                'active' : active_alarms,
            },
            'events' : {
                'new' : new_events if new_events else 0,
            }
        }
        return Response(data=data)

