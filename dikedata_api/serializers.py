# (c) Nelen & Schuurmans.  MIT licensed, see LICENSE.rst.
from __future__ import unicode_literals

from ddsc_core.models import Location, Timeseries
from django.contrib.auth.models import User, Group as Role
from django.contrib.gis.db import models
from rest_framework import serializers
from lizard_security.models import UserGroup


class BaseSerializer(serializers.HyperlinkedModelSerializer):
    pass


class UserListSerializer(BaseSerializer):
    class Meta:
        model = User
        fields = ('url', 'username', )


class UserDetailSerializer(BaseSerializer):
    class Meta:
        model = User
        exclude = ('password', 'groups', 'user_permissions', )


class GroupListSerializer(BaseSerializer):
    class Meta:
        model = UserGroup
        fields = ('url', 'name', )


class GroupDetailSerializer(BaseSerializer):
    class Meta:
        model = UserGroup


class RoleListSerializer(BaseSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='role-detail')
    class Meta:
        model = Role
        exclude = ('permissions', 'permission_mappers', )


class RoleDetailSerializer(BaseSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='role-detail')
    class Meta:
        model = Role
        exclude = ('permissions', 'permission_mappers', )


class LocationListSerializer(BaseSerializer):
    class Meta:
        model = Location
        fields = ('url', 'name', )


class LocationDetailSerializer(BaseSerializer):
    timeseries = serializers.ManyHyperlinkedRelatedField(
        view_name='timeseries-detail')

    class Meta:
        model = Location


class TimeseriesListSerializer(BaseSerializer):
    class Meta:
        model = Timeseries
        fields = ('url', 'name', )


class TimeseriesDetailSerializer(BaseSerializer):
    events = serializers.HyperlinkedIdentityField(
        view_name='event-list')
    latest_value = serializers.Field()
#    supplying_system = serializers.HyperlinkedRelatedField(
#        view_name='user-detail')

    class Meta:
        model = Timeseries
        exclude = (
            'supplying_system',
            'latest_value_number',
            'latest_value_text',
            'data_set',
        )
