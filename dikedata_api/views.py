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
from django.http import Http404, HttpResponse
from django.utils.decorators import method_decorator

from rest_framework import exceptions as ex, generics
from rest_framework.parsers import JSONParser, FormParser
from rest_framework.renderers import JSONRenderer, BrowsableAPIRenderer
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView
from rest_framework.pagination import PaginationSerializer
from rest_framework.exceptions import ParseError

import numpy as np

from tls import TLSRequestMiddleware

from lizard_security.models import DataSet, DataOwner, UserGroup

from ddsc_core.auth import PERMISSION_CHANGE
from ddsc_core.models import (Alarm, Alarm_Active, Alarm_Item, Location, LogicalGroup, LogicalGroupEdge, Source,
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


def customfilter(view, qs, filter_json, order_field=None):
    """
    Function for adding filters to queryset.
    set 'customfilter_fields for allowed fields'
    :param view:                view (self)
    :param qs:                  queryset
    :param filter_json:         raw_json of filter key. example is '{"name__contains": "bla", "uuid__startswith": "7"}'
    :return:
    """
    filter_fields = {}
    if view.customfilter_fields == '*':
        check_filter_fields = False
    else:
        check_filter_fields = True
        for item in view.customfilter_fields:

            if type(item) == tuple:
                filter_fields[item[0]] = item[1]
            else:
                filter_fields[item] = item

    exclude = False

    filter_dict = json.loads(filter_json)
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
        if check_filter_fields:
            if not key in filter_fields.keys():
                logger.warn('Property %s is not set for filtering.'%(key))
                #raise InvalidKey(key)
            elif  value:
                if exclude:
                    qs = qs.exclude(**{'%s__%s' % (filter_fields[key], lookup): value})
                else:
                    qs = qs.filter(**{'%s__%s' % (filter_fields[key], lookup): value})

    if order_field:
        order_field = order_field.replace('.','__')
        qs = qs.order_by(order_field)

    return qs


def order_by(view, qs, filter):
    pass


def write_events(user, data):
    if user is None:
        raise ex.NotAuthenticated("User not logged in.")
    reader = ListReader(data)
    series = {}
    permission = True
    locations = {}
    total = 0
    for (uuid, df) in reader.get_series():
        ts = Timeseries.objects.get(uuid=uuid)
        locations[ts.location_id] = 1
        series[uuid] = (ts, df)
        if not user.has_perm(PERMISSION_CHANGE, ts):
            permission = False
    if not permission:
        raise ex.PermissionDenied("Permission denied")
    for uuid, (ts, df) in series.items():
        ts.set_events(df)
        total += len(df)
        ts.save()
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
    def get_queryset(self):
        kwargs = {}
        qs = self.model.objects
        filter = self.request.QUERY_PARAMS.get('filter', None)
        order = self.request.QUERY_PARAMS.get('order', None)
        if filter:
            qs = customfilter(self, qs, filter, order)
        return qs.filter(**kwargs).distinct()


class APIListView(mixins.PostListModelMixin, APIReadOnlyListView):
    pass


class APIDetailView(mixins.BaseMixin, mixins.DetailModelMixin,
                    generics.SingleObjectAPIView):
    pass


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


class DataSetDetail(APIDetailView):
    model = DataSet
    serializer_class = serializers.DataSetDetailSerializer


class DataOwnerList(APIListView):
    model = DataOwner
    serializer_class = serializers.DataOwnerListSerializer


class DataOwnerDetail(APIDetailView):
    model = DataOwner
    serializer_class = serializers.DataOwnerDetailSerializer


class LocationList(APIListView):
    model = Location
    serializer_class = serializers.SubSubLocationSerializer

    customfilter_fields = ('uuid', 'name')

    def get_queryset(self):
        kwargs = {}
        qs = Location.objects

        filter = self.request.QUERY_PARAMS.get('filter', None)
        order = self.request.QUERY_PARAMS.get('order', None)
        if filter:
            qs = customfilter(self, qs, filter, order)

        parameter = self.request.QUERY_PARAMS.get('parameter', None)
        if parameter:
            kwargs['timeseries__parameter__in'] = parameter.split(',')
        logicalgroup = self.request.QUERY_PARAMS.get('logicalgroup', None)
        if logicalgroup:
            kwargs['timeseries__logical_groups__in'] = logicalgroup.split(',')
        has_geometry = self.request.QUERY_PARAMS.get('has_geometry', None)
        if has_geometry == 'true':
            kwargs['point_geometry__isnull'] = False
        return qs.filter(**kwargs).distinct()


class LocationDetail(APIDetailView):
    model = Location
    serializer_class = serializers.LocationDetailSerializer
    slug_field = 'uuid'
    slug_url_kwarg = 'uuid'


class TimeseriesList(APIListView):
    model = Timeseries
    serializer_class = serializers.TimeseriesListSerializer

    customfilter_fields = ('uuid', 'name', 'location__name', ('parameter', 'parameter__code'),
                           ('unit', 'unit__code'), ('dataowner', 'dataowner__name'))

    def get_queryset(self):
        kwargs = {}
        qs = Timeseries.objects

        filter = self.request.QUERY_PARAMS.get('filter', None)
        order = self.request.QUERY_PARAMS.get('order', None)
        if filter:
            qs = customfilter(self, qs, filter, order)

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
            df = ts.get_events(start=start, end=end, filter=filter)
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
            combined_ts = Timeseries.objects.get(uuid=combine_with)
            # returns an object ready for a jQuery scatter plot
            df_xaxis = ts.get_events(
                start=start,
                end=end,
                filter=filter).asfreq('1H', method='pad')
            df_yaxis = combined_ts.get_events(
                start=start,
                end=end,
                filter=filter).asfreq('1H', method='pad')
            response = self.scatter_plot(request, df_xaxis, df_yaxis, ts, combined_ts, start, end)
        elif eventsformat == 'flot':
            # only return in jQuery Flot compatible format when requested
            df = ts.get_events(start=start, end=end, filter=filter)
            response = self.format_flot(request, ts, df, start, end)

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
    def scatter_plot(request, df_xaxis, df_yaxis, ts, combined_ts, start, end):
        data = zip(df_xaxis['value'].values, df_yaxis['value'].values)
        line = {
            'label': '{} vs. {}'.format(ts, combined_ts),
            'data': data,
            # These are added to determine the axis which will be related
            # to the graph line.
            'parameter_name': '{} ({}) vs. {} ({})'.format(
                str(ts.parameter),
                str(ts.unit),
                str(combined_ts.parameter),
                str(combined_ts.unit)
            ),
            'parameter_pk': ts.parameter.pk,
            # These are used to reset the graph boundaries when the first
            # line is plotted.
            'xmin': None,
            'xmax': None
        }

        return line

    @staticmethod
    def format_flot(request, ts, df, start=None, end=None):
        tolerance = request.QUERY_PARAMS.get('tolerance', None)
        width = request.QUERY_PARAMS.get('width', None)
        height = request.QUERY_PARAMS.get('height', None)

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
            'parameter_name': '{} ({})'.format(str(ts.parameter), str(ts.unit)),
            'parameter_pk': ts.parameter.pk,
            # These are used to reset the graph boundaries when the first
            # line is plotted.
            'xmin': xmin,
            'xmax': xmax,
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
    customfilter_fields = ('uuid', 'name', ('manufacturer', 'manufacturer__name',), 'details', 'frequency', 'timeout' )


class SourceDetail(APIDetailView):
    model = Source
    serializer_class = serializers.SourceDetailSerializer
    slug_field = 'uuid'
    slug_url_kwarg = 'uuid'


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
            print item

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
            print item

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


class AlarmActiveDetail(APIDetailView):
    model = Alarm_Active
    serializer_class = serializers.Alarm_ActiveDetailSerializer


class AlarmSettingList(APIListView):
    model = Alarm
    serializer_class = serializers.AlarmSettingListSerializer

    def pre_save(self, obj):

        if obj.object_id is None:
            obj.object_id = self.request.user.id

    def post_save(self, obj, created=True):
        """
            custom function for saving nested alarm items
            This save method is not transaction save and without validation on the alarm_items.
            Please refactor this function when write support is added to django rest framework
            (work in progress at this moment)
        """
        cur_alarm_items = dict([(item.id, item) for item in obj.alarm_item_set.all()])

        req_alarm_items = self.request.DATA.getlist('alarm_item_set')

        for item in req_alarm_items:
            item = json.loads(item)
            if self.request.method == 'POST' or not 'id' in item or item['id'] is None:
                #create item
                item['alarm'] = obj.id
                alarm_item = serializers.AlarmItemDetailSerializer(None, data=item)
                alarm_item.is_valid()
                alarm_item.save()

            elif item['id'] in cur_alarm_items:
                #update
                cur_item = cur_alarm_items[item['id']]
                alarm_item = serializers.AlarmItemDetailSerializer(cur_item, data=item)
                alarm_item.is_valid()
                alarm_item.save()
                del cur_alarm_items[item['id']]

        #delete the leftovers
        for alarm_item in cur_alarm_items.values():
            alarm_item.delete()


class AlarmSettingDetail(APIDetailView):
    model = Alarm
    serializer_class = serializers.AlarmSettingDetailSerializer

    def pre_save(self, obj):

        if obj.object_id is None:
            obj.object_id = self.request.user.id

    def post_save(self, obj, created=True):
        """
            custom function for saving nested alarm items
            This save method is not transaction save and without validation on the alarm_items.
            Please refactor this function when write support is added to django rest framework
            (work in progress at this moment)
        """
        cur_alarm_items = dict([(item.id, item) for item in obj.alarm_item_set.all()])

        req_alarm_items = self.request.DATA.getlist('alarm_item_set')

        for item in req_alarm_items:
            item = json.loads(item)
            if self.request.method == 'POST' or not 'id' in item or item['id'] is None:
                #create item
                item['alarm'] = obj.id
                alarm_item = serializers.AlarmItemDetailSerializer(None, data=item)
                alarm_item.is_valid()
                alarm_item.save()

            elif item['id'] in cur_alarm_items:
                #update
                cur_item = cur_alarm_items[item['id']]
                alarm_item = serializers.AlarmItemDetailSerializer(cur_item, data=item)
                alarm_item.is_valid()
                alarm_item.save()
                del cur_alarm_items[item['id']]

        #delete the leftovers
        for alarm_item in cur_alarm_items.values():
            alarm_item.delete()

class AlarmItemDetail(APIDetailView):
    model = Alarm_Item
    serializer_class = serializers.AlarmItemDetailSerializer


class StatusCacheList(APIListView):
    model = StatusCache
    serializer_class = serializers.StatusCacheListSerializer
    customfilter_fields = ('id', 'timeseries__name', 'timeseries__parameter__code',
                           'nr_of_measurements_total', 'nr_of_measurements_reliable', 'nr_of_measurements_doubtful',
                           'nr_of_measurements_unreliable', 'min_val', 'max_val', 'mean_val', 'std_val', 'status_date')


class StatusCacheDetail(APIDetailView):
    model = StatusCache
    serializer_class = serializers.StatusCacheDetailSerializer
    customfilter_fields = ('id', 'timeseries__name', 'timeseries__parameter__code',
                           'nr_of_measurements_total', 'nr_of_measurements_reliable', 'nr_of_measurements_doubtful',
                           'nr_of_measurements_unreliable', 'min_val', 'max_val', 'mean_val', 'std_val', 'status_date')
