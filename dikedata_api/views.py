# (c) Nelen & Schuurmans.  MIT licensed, see LICENSE.rst.
from __future__ import unicode_literals

from ddsc_core.models import Location, Timeseries
from dikedata_api import serializers
from datetime import datetime
from dateutil.relativedelta import relativedelta
from dikedata_api.exceptions import APIException
from django.contrib.auth.models import User
from django.http import Http404
from django.utils.translation import ugettext as _
from lizard_ui.views import UiView
from lizard_security.models import UserGroup
from rabbitmqlib.models import Producer
from rest_framework import generics, mixins
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView


COLNAME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'


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
        try:
            return self.list(request, *args, **kwargs)
        except Exception as ex:
            raise APIException(ex)


class APIDetailView(mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                    mixins.DestroyModelMixin, generics.SingleObjectAPIView):
    def get(self, request, *args, **kwargs):
        try:
            return self.retrieve(request, *args, **kwargs)
        except Exception as ex:
            raise APIException(ex)


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


class EventList(APIDetailView):

    def retrieve(self, request, pk=None, format=None):
        result = Timeseries.objects.filter(code=pk)
        if len(result) == 0:
            raise Http404("Geen timeseries gevonden die voldoet aan de query")
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
