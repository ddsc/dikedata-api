# (c) Nelen & Schuurmans.  MIT licensed, see LICENSE.rst.
from __future__ import unicode_literals

from ddsc_core.models import Location, Timeseries
from dikedata_api import serializers
from datetime import datetime
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib.auth.models import User
from django.utils.translation import ugettext as _
from lizard_ui.views import UiView
from lizard_security.models import UserGroup
from cassandralib.models import CassandraDataStore
from rabbitmqlib.models import Producer
from rest_framework import mixins
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView

import pandas as pd
import pytz
import sys
import traceback
import uuid


SERVERS = settings.CASSANDRA['servers']
KEYSPACE = settings.CASSANDRA['keyspace']
COL_FAM = settings.CASSANDRA['column_family']
COLNAME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
INTERNAL_TIMEZONE = pytz.UTC

class ExceptionResponse(Response):
    def __init__(self, ex):
        super(ExceptionResponse, self).__init__()
        exc_type, exc_value, exc_traceback = sys.exc_info()
        trace = traceback.extract_tb(exc_traceback)
        print trace
        (file, line, method, expr) = trace[-1]
        error = '%s: %s in %s, line %d' % (ex.__class__.__name__,
            ', '.join(ex.args), file, line)
        self.data = {'error': error}
    
    def __repr__(self):
        return repr(self.data)

class Root(APIView):
    """
    The entry endpoint of our API.
    """
    def get(self, request, format=None):
        return Response({
            'users': reverse('user-list', request=request),
            'groups': reverse('usergroup-list', request=request),
            'locations': reverse('location-list', request=request),
            'timeseries': reverse('timeseries-list', request=request),
        })

class APIListView(mixins.ListModelMixin, mixins.CreateModelMixin,
                    generics.MultipleObjectAPIView):
    def get(self, request, *args, **kwargs):
#        try:
            return self.list(request, *args, **kwargs)
#        except Exception as ex:
#            return ExceptionResponse(ex)

class APIDetailView(mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                    mixins.DestroyModelMixin, generics.SingleObjectAPIView):
    def get(self, request, *args, **kwargs):
#        try:
            return self.retrieve(request, *args, **kwargs)
#        except Exception as ex:
#            return ExceptionResponse(ex)

class UserList(APIListView):
    model = User
    serializer_class = serializers.UserListSerializer

class UserDetail(APIDetailView):
    model = User
    serializer_class = serializers.UserDetailSerializer

class GroupList(APIListView):
    model = UserGroup
    serializer_class = serializers.GroupListSerializer

class GroupDetail(APIDetailView):
    model = UserGroup
    serializer_class = serializers.GroupDetailSerializer

class LocationList(APIListView):
    model = Location
    serializer_class = serializers.LocationListSerializer

class LocationDetail(APIDetailView):
    model = Location
    serializer_class = serializers.LocationDetailSerializer

class TimeseriesList(APIListView):
    model = Timeseries
    serializer_class = serializers.TimeseriesListSerializer

class TimeseriesDetail(APIDetailView):
    model = Timeseries
    serializer_class = serializers.TimeseriesDetailSerializer

class TimeseriesData(APIDetailView):
    model = Timeseries
    serializer_class = serializers.TimeseriesDataSerializer

#deprecated
def timeseries_data(request, series_code):
    cassandra = CassandraDataStore(SERVERS, KEYSPACE, COL_FAM, 10000)
    
    get = request.GET.keys()
    try:
        params = {}
        if 'start' in params:
            start = datetime.strptime(params['start'], COLNAME_FORMAT)
        else:
            start = datetime.now() + relativedelta( years = -3 )
        if 'end' in params:
            end = datetime.strptime(params['end'], COLNAME_FORMAT)
        else:
            end = datetime.now()
        filter = ['value', 'flag']

        df = cassandra.read(series_code,
            INTERNAL_TIMEZONE.localize(start),
            INTERNAL_TIMEZONE.localize(end), params=filter)
        
        data = [
            dict([('datetime', timestamp.strftime(COLNAME_FORMAT))] + [
                (colname, row[i])
                for i, colname in enumerate(df.columns)
            ])
            for timestamp, row in df.iterrows()
        ]
        return data

    except Exception as ex:
        print repr(ExceptionResponse(ex))
        return []

#deprecated
def api_write(request):
    msg = {}
    get = request.GET.keys()
    try:
        if not 'request' in get:
            raise Exception("Missing GET parameter 'request'")
        params = json.loads(request.GET.get('request'))
        if not 'timeseries' in params:
            raise Exception("Missing parameter 'timeseries'")
        timeseries = params['timeseries']
        msg = {'timeseries': timeseries}

        # Store time series in Cassandra
        for series_id in timeseries:
            datetimes = []
            data = []
            for datum in timeseries[series_id]:
                if "datetime" in datum:
                    dt = datetime.strptime(datum["datetime"], COLNAME_FORMAT)
                    datetimes.append(dt.replace(tzinfo=INTERNAL_TIMEZONE))
                    del datum["datetime"]
                    data.append(datum)
            df = pd.DataFrame(data=data, index=datetimes)
            cassandra = CassandraDataStore(
                settings.CASSANDRA['servers'],
                settings.CASSANDRA['keyspace'],
                settings.CASSANDRA['column_family'],
                10000
            )
            cassandra.write(series_id, df)

        # Inform Rabbit MQ
        msg['message_id'] = str(uuid.uuid4())
        producer = Producer(settings.RABBITMQ['server'],
            settings.RABBITMQ['user'], settings.RABBITMQ['password'],
            settings.RABBITMQ['vhost'])
        producer.send(msg, b"timeseries", b"store")
        msg['status'] = 'OK'
    except Exception as ex:
        msg['error'] = ex.__class__.__name__ + ': ' + ', '.join(ex.args)

    return HttpResponse(json.dumps(msg, indent=4), mimetype='application/json')
