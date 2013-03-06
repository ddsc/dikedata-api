# (c) Nelen & Schuurmans.  MIT licensed, see LICENSE.rst.
from __future__ import unicode_literals

from ddsc_core.models import Location, Timeseries, Parameter, LogicalGroup
from dikedata_api import fields
from django.contrib.auth.models import User, Group as Role
from django.core.exceptions import ValidationError
from rest_framework import serializers
from lizard_security.models import DataOwner, DataSet, UserGroup


class BaseSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.Field('id')


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
        view_name='timeseries-detail', slug_field='uuid')

    class Meta:
        model = DataSet


class DataOwnerListSerializer(BaseSerializer):
    class Meta:
        model = DataOwner


class DataOwnerDetailSerializer(BaseSerializer):
    class Meta:
        model = DataOwner


class ParameterListSerializer(BaseSerializer):

    class Meta:
        model = Parameter
        fields = ('id', 'url', 'code', 'description')


class ParameterDetailSerializer(BaseSerializer):

    class Meta:
        model = Parameter
        fields = ('id', 'url', 'code', 'description', 'cas_number', 'group',
            'sikb_id')


class SubSubLocationSerializer(BaseSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='location-detail', slug_field='uuid')
    point_geometry = serializers.Field()

    class Meta:
        model = Location
        fields = ('url', 'name', 'description', 'point_geometry')


class SubLocationSerializer(SubSubLocationSerializer):
    sublocations = SubSubLocationSerializer(source='sublocations')

    class Meta:
        model = Location
        fields = (
            'url',
            'uuid',
            'name',
            'point_geometry',
            'sublocations',
        )


class LocationListSerializer(SubLocationSerializer):
    sublocations = SubLocationSerializer(source='sublocations')


class LocationDetailSerializer(SubSubLocationSerializer):
    timeseries = serializers.ManyHyperlinkedRelatedField(
        view_name='timeseries-detail', slug_field='uuid')
    superlocation = fields.HyperlinkedRelatedMethod(
        view_name='location-detail', slug_field='uuid', read_only=True)
    sublocations = fields.ManyHyperlinkedRelatedMethod(
        view_name='location-detail', slug_field='uuid', read_only=True)
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


class TimeseriesListSerializer(BaseSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='timeseries-detail', slug_field='uuid')
    events = serializers.HyperlinkedIdentityField(
        view_name='event-list', slug_field='uuid')
    value_type = serializers.Field('get_value_type')
    latest_value = fields.LatestValue(view_name='event-detail')
    parameter = fields.RelatedField(model_field='id')
    location = fields.RelatedField(model_field='uuid')
    logical_groups = fields.ManyRelatedField(model_field='id')

    class Meta:
        model = Timeseries
        fields = ('url', 'uuid', 'events', 'latest_value', 'name', 'value_type',
                  'parameter', 'location', 'logical_groups')


class TimeseriesDetailSerializer(BaseSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='timeseries-detail', slug_field='uuid')
    location = serializers.HyperlinkedRelatedField(
        view_name='location-detail', slug_field='uuid')
    events = serializers.HyperlinkedIdentityField(
        view_name='event-list', slug_field='uuid')
    value_type = serializers.Field('get_value_type')
    latest_value = fields.LatestValue(view_name='event-detail')

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
            'parameter',
        )
        depth = 1


class EventListSerializer(serializers.Serializer):

    class Meta:
        pass

    def mandatory_fields(self):
        return {
            "datetime": serializers.WritableField(),
            "value": serializers.WritableField(),
        }

    def restore_fields(self, data, files):
        if data is not None and not isinstance(data, dict):
            self._errors['non_field_errors'] = [u'Invalid data']
            return None

        for field_name, field in self.mandatory_fields().items():
            try:
                field.validate(data.get(field_name))
            except ValidationError as err:
                self._errors[field_name] = list(err.messages)

        return data

    def to_native(self, obj):
        return obj


class MultiEventListSerializer(serializers.Serializer):

    class Meta:
        pass

    def mandatory_fields(self):
        return {
            "uuid": serializers.WritableField(),
            "events": EventListSerializer(),
        }

    def restore_fields(self, data, files):
        if data is not None and not isinstance(data, dict):
            self._errors['non_field_errors'] = [u'Invalid data']
            return None

        for field_name, field in self.mandatory_fields().items():
            try:
                field.validate(data.get(field_name))
            except ValidationError as err:
                self._errors[field_name] = list(err.messages)

        return data

    def to_native(self, obj):
        return obj


class LogicalGroupListSerializer(BaseSerializer):
    class Meta:
        model = LogicalGroup
        fields = ('id', 'url', 'name',)


class LogicalGroupDetailSerializer(BaseSerializer):
    timeseries = serializers.ManyHyperlinkedRelatedField(
        view_name='timeseries-detail', slug_field='uuid')
    parents = fields.ManyHyperlinkedParents(
        view_name='logicalgroup-detail', read_only=True)
    childs = fields.ManyHyperlinkedChilds(
        view_name='logicalgroup-detail', read_only=True)

    class Meta:
        model = LogicalGroup
