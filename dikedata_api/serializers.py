# (c) Nelen & Schuurmans.  MIT licensed, see LICENSE.rst.
from __future__ import unicode_literals

from ddsc_core.models import (Alarm, Alarm_Active, Alarm_Item, Location, LogicalGroup, LogicalGroupEdge,
                              Manufacturer, Timeseries, Source )
from dikedata_api import fields
from django.contrib.auth.models import User, Group as Role
from django.core.exceptions import ValidationError
from rest_framework import serializers
from lizard_security.models import DataOwner, DataSet, UserGroup
from django.contrib.contenttypes.models import ContentType


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


class ManufacturerListSerializer(BaseSerializer):

    class Meta:
        model = Manufacturer
        fields = ('code', 'name')


class SourceListSerializer(BaseSerializer):
    manufacturer = ManufacturerListSerializer()

    class Meta:
        model = Source
        fields = ('name', 'source_type', 'manufacturer')
        depth = 1



class Alarm_ActiveListSerializer(BaseSerializer):

    class Meta:
        model = Alarm_Active


class AlarmDetailSerializer(BaseSerializer):
    # alarm = serializers.SerializerMethodField('get_alarm_type')

    class Meta:
        model = Alarm
        depth = 2

class Alarm_ActiveDetailSerializer(BaseSerializer):
    alarm = AlarmDetailSerializer()
    alarm_type = serializers.SerializerMethodField('get_alarm_type')

    def get_alarm_type(self, obj):
        try:
            alarmitems = obj.alarm.alarm_item_set.get()
            alarm_type = alarmitems.alarm_type
        except:
            alarm_object = 'No Alarm type found'
            return alarm_object
        try:
            alarm_object = alarm_type.get_object_for_this_type()
        except:
            alarm_object = 'invalid instance of {}'.format(alarm_type)
        return alarm_object

    class Meta:
        model = Alarm_Active
        depth = 2


class ModelRefSerializer(serializers.SlugRelatedField):

    class Meta:
        model = ContentType


class AlarmItemDetailSerializer(BaseSerializer):

    comparision = fields.DictChoiceField(choices=Alarm_Item.COMPARISION_TYPE)
    logical_check = fields.DictChoiceField(choices=Alarm_Item.LOGIC_TYPES)
    value_type = fields.DictChoiceField(choices=Alarm_Item.VALUE_TYPE)
    alarm_type = ModelRefSerializer(slug_field = 'name')

    class Meta:
        model = Alarm_Item
        exclude = ('alarm', )


class AlarmSettingDetailSerializer(BaseSerializer):
    alarm_item_set = AlarmItemDetailSerializer(many=True, read_only=True)
    frequency = fields.DictChoiceField(choices=Alarm.FREQUENCY_TYPE)
    urgency = fields.DictChoiceField(choices=Alarm.URGENCY_TYPE)
    logical_check = fields.DictChoiceField(choices=Alarm.LOGIC_TYPES)
    message_type = fields.DictChoiceField(choices=Alarm.MESSAGE_TYPE)

    class Meta:
        model = Alarm
        exclude = ('single_or_group', )
        read_only = ('previous_alarm')


class AlarmSettingListSerializer(AlarmSettingDetailSerializer):

    url = serializers.HyperlinkedIdentityField(
        view_name='alarm-detail')

    class Meta:
        model = Alarm
        fields = (
            'url',
            'id',
            'name',
            #'single_or_group',
            'object_id',
            'frequency',
            'urgency',
            'message_type',
            'active_status',
        )


class SubSubLocationSerializer(BaseSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='location-detail', slug_field='uuid')
    point_geometry = serializers.Field()

    class Meta:
        model = Location
        fields = ('url',
                  'uuid',
                  'name',
                  'description',
                  'point_geometry',
                  'path',
                  'depth',)


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
            'uuid',
            'name',
            'description',
            'point_geometry',
            'geometry_precision',
            'relative_location',
            #'real_geometry',
            'created',
            'path',
            'depth',
            'superlocation',
            'sublocations',
            'timeseries',
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
        fields = ('id', 'url', 'uuid', 'events', 'latest_value', 'name', 'value_type',
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
    first_value_timestamp = fields.DateTimeField()
    latest_value_timestamp = fields.DateTimeField()
    source = SourceListSerializer()
    parameter = fields.AquoField()
    unit = fields.AquoField()
    reference_frame = fields.AquoField()
    compartment = fields.AquoField()
    measuring_device = fields.AquoField()
    measuring_method = fields.AquoField()
    processing_method = fields.AquoField()

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
            'parameter',
            'unit',
            'reference_frame',
            'compartment',
            'measuring_device',
            'measuring_method',
            'processing_method',
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


class TimeseriesRefSerializer(serializers.HyperlinkedRelatedField):

    class Meta:
        model = Timeseries

    def field_to_native(self, obj, field):
        #get display value
        return [{'url': self.to_native(t), 'name': t.name} for t in getattr(obj, field).all()]




class LogicalGroupParentRefSerializer(BaseSerializer):

    name = serializers.SerializerMethodField('get_name')

    def get_name(self, obj):
        return obj.parent.name

    class Meta:
        model = LogicalGroupEdge
        fields = ('id', 'parent', 'name')


    # def field_to_native(self, obj, field):
    #     """
    #         return dict representation of model
    #     """
    #     return [{'url': t.parent, 'name': t.parent.name} for t in getattr(obj, field).all()]


class DataOwnerRefSerializer(serializers.SlugRelatedField):

    class Meta:
        model = DataOwner

class LogicalGroupDetailSerializer(BaseSerializer):
    id = serializers.Field('id')
    timeseries = TimeseriesRefSerializer(many=True, view_name='timeseries-detail', slug_field='uuid')
    parents = LogicalGroupParentRefSerializer(many=True, read_only=True)
    childs = fields.ManyHyperlinkedChilds(
        view_name='logicalgroup-detail', read_only=True)
    owner = DataOwnerRefSerializer(slug_field='name')

    class Meta:
        model = LogicalGroup


class LogicalGroupListSerializer(LogicalGroupDetailSerializer):

    parents = fields.ManyHyperlinkedParents(many=True,
        view_name='logicalgroup-detail', slug_field='id')

    class Meta:
        model = LogicalGroup
        fields = ('id', 'url', 'name', 'parents')
