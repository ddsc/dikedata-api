# (c) Nelen & Schuurmans.  MIT licensed, see LICENSE.rst.
from __future__ import unicode_literals

from ddsc_core.models import LocationGroup, Location, Timeseries
from django.contrib.auth.models import User, Group as Role
from django.contrib.gis.db import models
from rest_framework import serializers
from lizard_security.models import DataSet, UserGroup


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


class DataSetListSerializer(BaseSerializer):
    class Meta:
        model = DataSet


class DataSetDetailSerializer(BaseSerializer):
    timeseries = serializers.ManyHyperlinkedRelatedField(
        view_name='timeseries-detail', slug_field='code')

    class Meta:
        model = DataSet


class LocationGroupListSerializer(BaseSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='locationgroup-detail')
    class Meta:
        model = LocationGroup
        fields = ('url', 'name', )


class LocationGroupDetailSerializer(BaseSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='locationgroup-detail')
    locations = serializers.ManyHyperlinkedRelatedField(
        view_name='location-detail', slug_field='code')

    class Meta:
        model = LocationGroup


class LocationListSerializer(BaseSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='location-detail', slug_field='code')

    class Meta:
        model = Location
        fields = ('url', 'name', )


class LocationDetailSerializer(BaseSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='location-detail', slug_field='code')
    timeseries = serializers.ManyHyperlinkedRelatedField(
        view_name='timeseries-detail', slug_field='code')
    sublocations = serializers.SerializerMethodField(
        'get_sublocations')
    location_groups = serializers.ManyHyperlinkedRelatedField(
        view_name='locationgroup-detail')

    class Meta:
        model = Location
        exclude = (
            'path',
            'depth',
            'numchild',
        )

    def get_sublocations(self, obj):
        return obj.get_children()


class TimeseriesListSerializer(BaseSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='timeseries-detail', slug_field='code')
    latest_value = serializers.Field()

    class Meta:
        model = Timeseries
        fields = ('url', 'name', 'value_type', 'latest_value', )


class TimeseriesDetailSerializer(BaseSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='timeseries-detail', slug_field='code')
    location = serializers.HyperlinkedRelatedField(
        view_name='location-detail', slug_field='code')
    events = serializers.HyperlinkedIdentityField(
        view_name='event-list', slug_field='code')
    latest_value = serializers.Field()
#    supplying_system = serializers.HyperlinkedRelatedField(
#        view_name='user-detail')

    class Meta:
        model = Timeseries
        exclude = (
            'supplying_system',
            'latest_value_number',
            'latest_value_text',
            'parameter',
            'unit',
            'reference_frame',
            'compartment',
            'measuring_device',
            'measuring_method',
            'processing_method',
        )
