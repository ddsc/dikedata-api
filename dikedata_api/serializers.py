# (c) Nelen & Schuurmans.  MIT licensed, see LICENSE.rst.
from __future__ import unicode_literals

from ddsc_core.models import Location, Timeseries, Parameter
from django.contrib.auth.models import User, Group as Role
from rest_framework import serializers
from lizard_security.models import DataOwner, DataSet, UserGroup


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


class DataOwnerListSerializer(BaseSerializer):
    class Meta:
        model = DataOwner


class DataOwnerDetailSerializer(BaseSerializer):
    class Meta:
        model = DataOwner


class LocationListSerializer(BaseSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='location-detail', slug_field='uuid')
    timeseries = serializers.ManyHyperlinkedRelatedField(
        view_name='timeseries-detail', slug_field='uuid')
    point_geometry = serializers.Field()

    class Meta:
        model = Location
        fields = (
            'url',
            'timeseries',
            'point_geometry',
            'uuid',
            'name',
        )


class LocationDetailSerializer(BaseSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='location-detail', slug_field='uuid')
    timeseries = serializers.ManyHyperlinkedRelatedField(
        view_name='timeseries-detail', slug_field='uuid')
    superlocation = serializers.SerializerMethodField('get_superlocation')
    sublocations = serializers.SerializerMethodField('get_sublocations')
    point_geometry = serializers.Field()

    class Meta:
        model = Location
        fields = (
            'url',
            'timeseries',
            'superlocation',
            'sublocations',
            'point_geometry',
            'uuid',
            'name',
            'description',
        )
        depth = 10

    def get_superlocation(self, obj):
        return obj.get_parent()

    def get_sublocations(self, obj):
        return obj.get_children()


class TimeseriesListSerializer(BaseSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='timeseries-detail', slug_field='uuid')
    latest_value = serializers.Field()

    class Meta:
        model = Timeseries
        fields = ('url', 'name', 'value_type', 'latest_value', )


class TimeseriesDetailSerializer(BaseSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='timeseries-detail', slug_field='uuid')
    location = serializers.HyperlinkedRelatedField(
        view_name='location-detail', slug_field='uuid')
    events = serializers.HyperlinkedIdentityField(
        view_name='event-list', slug_field='uuid')
    latest_value = serializers.Field()

    class Meta:
        model = Timeseries
        fields = (
            'url',
            'location',
            'events',
            'latest_value',
            'uuid',
            'name',
            'description',
            'value_type',
            'source',
            'owner',
            'first_value_timestamp',
            'latest_value_timestamp',
            'supplying_systems',
        )


class ParameterListSerializer(BaseSerializer):

    class Meta:
        model = Parameter
        exclude = ('url',)
