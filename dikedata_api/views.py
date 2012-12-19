# (c) Nelen & Schuurmans.  MIT licensed, see LICENSE.rst.
from __future__ import unicode_literals

from ddsc_core.models import Location, Timeseries
from dikedata_api import serializers
from datetime import datetime
from dateutil.relativedelta import relativedelta
from dikedata_api.exceptions import APIException
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User, Group as Role
from django.http import Http404
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from lizard_ui.views import UiView
from lizard_security.models import UserGroup
from lizard_security.backends import LizardPermissionBackend
from rest_framework import generics, mixins
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView


COLNAME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
LOGIN_URL = '/api/auth/login/'


class Root(APIView):
    """
    The entry endpoint of our API.
    """
    def get(self, request, format=None):
        response = {
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


class Protected(object):
    @method_decorator(permission_required('staff', LOGIN_URL))
    def dispatch(self, request, *args, **kwargs):
        return super(Protected, self).dispatch(request, *args, **kwargs)


class APIListView(mixins.ListModelMixin,
                  mixins.CreateModelMixin,
                  generics.MultipleObjectAPIView):
    def get(self, request, *args, **kwargs):
        try:
            return self.list(request, *args, **kwargs)
        except Exception as ex:
            raise APIException(ex)

    @method_decorator(permission_required('add', LOGIN_URL))
    def post(self, request, *args, **kwargs):
        try:
            return self.create(request, *args, **kwargs)
        except Exception as ex:
            raise APIException(ex)


class APIDetailView(mixins.RetrieveModelMixin,
                    mixins.UpdateModelMixin,
                    mixins.DestroyModelMixin,
                    generics.SingleObjectAPIView):

    def get(self, request, *args, **kwargs):
        try:
            return self.retrieve(request, *args, **kwargs)
        except Exception as ex:
            raise APIException(ex)

    @method_decorator(permission_required('change', LOGIN_URL))
    def put(self, request, *args, **kwargs):
        try:
            return self.update(request, *args, **kwargs)
        except Exception as ex:
            raise APIException(ex)

    @method_decorator(permission_required('delete', LOGIN_URL))
    def delete(self, request, *args, **kwargs):
        try:
            return self.destroy(request, *args, **kwargs)
        except Exception as ex:
            raise APIException(ex)


class UserList(Protected, APIListView):
    model = User
    serializer_class = serializers.UserListSerializer


class UserDetail(Protected, APIDetailView):
    model = User
    serializer_class = serializers.UserDetailSerializer


class GroupList(Protected, APIListView):
    model = UserGroup
    serializer_class = serializers.GroupListSerializer


class GroupDetail(Protected, APIDetailView):
    model = UserGroup
    serializer_class = serializers.GroupDetailSerializer


class RoleList(Protected, APIListView):
    model = Role
    serializer_class = serializers.RoleListSerializer


class RoleDetail(Protected, APIDetailView):
    model = Role
    serializer_class = serializers.RoleDetailSerializer


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
