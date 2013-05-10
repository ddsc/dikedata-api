# (c) Nelen & Schuurmans.  MIT licensed, see LICENSE.rst.
from __future__ import unicode_literals

from ddsc_core.models import (Alarm, Alarm_Active, Alarm_Item, Location, LogicalGroup, LogicalGroupEdge,
                              Manufacturer, Timeseries, Source, StatusCache )
from ddsc_core.models.aquo import Compartment
from ddsc_core.models.aquo import MeasuringDevice
from ddsc_core.models.aquo import MeasuringMethod
from ddsc_core.models.aquo import Parameter
from ddsc_core.models.aquo import ProcessingMethod
from ddsc_core.models.aquo import ReferenceFrame
from ddsc_core.models.aquo import Unit

from dikedata_api import fields
from django.contrib.auth.models import User, Group as Role
from django.core.exceptions import ValidationError
from rest_framework import serializers
from rest_framework import fields as rest_fields
from lizard_security.models import DataOwner, DataSet, UserGroup, PermissionMapper
from django.contrib.contenttypes.models import ContentType


class BaseSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.Field('id')


class ParameterSerializer(serializers.ModelSerializer):

    class Meta:
        model = Parameter
        fields = ('id', 'code', 'description', 'group', )


class CompartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Compartment
        fields = ('id', 'code', 'description')


class MeasuringDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeasuringDevice
        fields = ('id', 'code', 'description')


class MeasuringMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeasuringMethod
        fields = ('id', 'code', 'description')


class ProcessingMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcessingMethod
        fields = ('id', 'code', 'description')


class ReferenceFrameSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferenceFrame
        fields = ('id', 'code', 'description')


class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = ('id', 'code', 'description')


class AquoRelatedSerializer(serializers.SlugRelatedField):
    """
    Base class for aquo refered fields
    """
    def field_to_native(self, obj, field):

        item = getattr(obj, field)
        if item:
            return {'id': item.id, 'code': item.code, 'description': item.description}

class ParameterRelSerializer(AquoRelatedSerializer):
    """
    """
    class Meta:
        model = Parameter
        fields = ('id', 'code', 'description')


class CompartmentRelSerializer(AquoRelatedSerializer):
    class Meta:
        model = Compartment
        fields = ('id', 'code', 'description')


class MeasuringDeviceRelSerializer(AquoRelatedSerializer):
    class Meta:
        model = MeasuringDevice
        fields = ('id', 'code', 'description')


class MeasuringMethodRelSerializer(AquoRelatedSerializer):
    class Meta:
        model = MeasuringMethod
        fields = ('id', 'code', 'description')


class ProcessingMethodRelSerializer(AquoRelatedSerializer):
    class Meta:
        model = ProcessingMethod
        fields = ('id', 'code', 'description')


class ReferenceFrameRelSerializer(AquoRelatedSerializer):
    class Meta:
        model = ReferenceFrame
        fields = ('id', 'code', 'description')


class UnitRelSerializer(AquoRelatedSerializer):
    class Meta:
        model = Unit
        fields = ('id', 'code', 'description')


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


class DataOwnerListSerializer(BaseSerializer):
    class Meta:
        model = DataOwner
        fields = ('id', 'url', 'name', )


class DataOwnerDetailSerializer(BaseSerializer):
    class Meta:
        model = DataOwner
        fields = ('id', 'url', 'name', 'remarks', )


class DataOwnerRefSerializer(serializers.SlugRelatedField):

    class Meta:
        model = DataOwner


class ManufacturerSerializer(BaseSerializer):
    class Meta:
        model = Manufacturer
        fields = ('code', 'name')


class ManufacturerRefSerializer(serializers.SlugRelatedField):
    class Meta:
        model = Manufacturer
        fields = ('code', 'name')


class SourceListSerializer(BaseSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='source-detail', slug_field='uuid')
    manufacturer = ManufacturerRefSerializer(slug_field='name')
    source_type = fields.DictChoiceField(choices=Source.SOURCE_TYPES)

    class Meta:
        model = Source
        fields = ('id', 'uuid', 'url', 'name', 'source_type', 'manufacturer', 'details', 'frequency', 'timeout')


class SourceDetailSerializer(SourceListSerializer):

    class Meta:
        model = Source
        fields = ('id', 'uuid', 'url', 'name', 'source_type', 'manufacturer', 'details', 'frequency', 'timeout')


class SourceRefSerializer(serializers.SlugRelatedField):

    class Meta:
        model = Source
        fields = ('uuid', 'url', 'name', 'source_type', 'manufacturer')

    def field_to_native(self, obj, field):
        item = getattr(obj, field)
        if item:
            return {'uuid': item.uuid, 'name': item.name}




class AlarmDetailSerializer(BaseSerializer):
    # alarm = serializers.SerializerMethodField('get_alarm_type')

    class Meta:
        model = Alarm
        #depth = 2


class ModelRefSerializer(serializers.SlugRelatedField):

    class Meta:
        model = ContentType

class AlarmSettingRefSerializer(serializers.SlugRelatedField):

    class Meta:
        model = Alarm


class AlarmItemDetailSerializer(BaseSerializer):

    comparision = fields.DictChoiceField(choices=Alarm_Item.COMPARISION_TYPE)
    logical_check = fields.DictChoiceField(choices=Alarm_Item.LOGIC_TYPES)
    value_type = fields.DictChoiceField(choices=Alarm_Item.VALUE_TYPE)
    alarm_type = ModelRefSerializer(slug_field = 'name')
    alarm = AlarmSettingRefSerializer(slug_field='id')

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
        exclude = ('single_or_group', 'previous_alarm', )
        read_only = ('previous_alarm', )


class AlarmSettingListSerializer(AlarmSettingDetailSerializer):

    url = serializers.HyperlinkedIdentityField(
        view_name='alarm-detail')
    single_or_group = ModelRefSerializer(slug_field='name')

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


class Alarm_ActiveDetailSerializer(BaseSerializer):
    alarm = AlarmSettingListSerializer()

    class Meta:
        model = Alarm_Active
        depth = 1


class Alarm_ActiveListSerializer(Alarm_ActiveDetailSerializer):

    class Meta:
        model = Alarm_Active



#
# class SubLocationSerializer(SubSubLocationSerializer):
#     sublocations = SubSubLocationSerializer(source='sublocations')
#
#     class Meta:
#         model = Location
#         fields = ('id',
#                   'url',
#                   'uuid',
#                   'name',
#                   'point_geometry',
#                   'sublocations',)


# class LocationListSerializer(SubLocationSerializer):
#     sublocations = SubLocationSerializer(source='sublocations')


class LocationDetailSerializer(BaseSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='location-detail', slug_field='uuid')
    timeseries = serializers.ManyHyperlinkedRelatedField(
        view_name='timeseries-detail', slug_field='uuid')
    superlocation = fields.HyperlinkedRelatedMethod(
        view_name='location-detail', slug_field='uuid', read_only=True)
    sublocations = fields.ManyHyperlinkedRelatedMethod(
        view_name='location-detail', slug_field='uuid', read_only=True)
    point_geometry = fields.GeometryPointField()
    srid = serializers.Field(source='get_srid')

    def save_object(self, obj, **kwargs):
        obj.save_under(parent_pk=None)

    class Meta:
        model = Location
        fields = (
            'id',
            'url',
            'uuid',
            'name',
            'description',
            'point_geometry',
            'geometry_precision',
            'srid',
            'relative_location',
            #'real_geometry',
            'created',
            'path',
            'depth',
            'superlocation',
            'sublocations',
            'timeseries',
        )
        read_only_fields = (
            'path',
            'created',
            'depth',
        )


class LocationListSerializer(LocationDetailSerializer):

    class Meta:
        model = Location
        fields = ('id',
                  'url',
                  'uuid',
                  'name',
                  'description',
                  'point_geometry',
                  'srid',
                  'path',
                  'depth',)

        read_only_fields = (
            'path',
            'depth',
        )


class LocationRefSerializer(serializers.SlugRelatedField):
    url = serializers.HyperlinkedIdentityField(
        view_name='location-detail', slug_field='uuid')

    class Meta:
        model = Location

    def field_to_native(self, obj, field):
        item = getattr(obj, field)
        if item:
            return {'uuid': item.uuid, 'name': item.name}


class TimeseriesDetailSerializer(BaseSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='timeseries-detail', slug_field='uuid')
    location = LocationRefSerializer(slug_field='uuid')
    source = SourceRefSerializer(slug_field='uuid')
    events = serializers.HyperlinkedIdentityField(
        view_name='event-list', slug_field='uuid')
    opendap = fields.OpenDAPLink()
    value_type = fields.DictChoiceField(choices=Timeseries.VALUE_TYPE)

    latest_value = fields.LatestValue(view_name='event-detail')
    first_value_timestamp = fields.DateTimeField()
    latest_value_timestamp = fields.DateTimeField()
    owner = DataOwnerRefSerializer(slug_field='name')

    #source = SourceListSerializer()
    parameter = ParameterRelSerializer(slug_field='code')
    unit = UnitRelSerializer(slug_field='code')
    reference_frame = ReferenceFrameRelSerializer(slug_field='code')
    compartment = CompartmentRelSerializer(slug_field='code')
    measuring_device = MeasuringDeviceRelSerializer(slug_field='code')
    measuring_method = MeasuringMethodRelSerializer(slug_field='code')
    processing_method = ProcessingMethodRelSerializer(slug_field='code')

    class Meta:
        model = Timeseries
        depth = 2
        fields = (
            'id',
            'url',
            'location',
            'events',
            'opendap',
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
            'validate_max_hard',
            'validate_min_hard',
            'validate_max_soft',
            'validate_min_soft',
            'validate_diff_hard',
            'validate_diff_soft'
        )
        #depth = 1,
        read_only = ('id', 'uuid', 'first_value_timestamp', 'latest_value_timestamp', 'latest_value', )


class TimeseriesListSerializer(TimeseriesDetailSerializer):
    unit = serializers.SlugRelatedField(slug_field='code')
    parameter = serializers.SlugRelatedField(slug_field='code')
    #location = fields.RelatedField(model_field='uuid')

    class Meta:
        model = Timeseries
        fields = ('id', 'url', 'uuid', 'name', 'location', 'latest_value_timestamp', 'latest_value', 'events', 'value_type',
                  'parameter', 'unit', 'owner', 'source')
        depth = 2


class TimeseriesSmallListSerializer(TimeseriesDetailSerializer):
    unit = serializers.SlugRelatedField(slug_field='code')
    parameter = serializers.SlugRelatedField(slug_field='code')
    #location = fields.RelatedField(model_field='uuid')


    class Meta:
        model = Timeseries
        fields = ('id', 'url', 'uuid', 'name', 'parameter', 'latest_value', 'value_type',)
        #depth = 2


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


class RoleSerializer(serializers.SlugRelatedField):

    class Meta:
        model = Role

class UserGroupSerializer(serializers.SlugRelatedField):

    class Meta:
        model = UserGroup



class PermissionMapperSerializer(serializers.ModelSerializer):
    permission_group = RoleSerializer(slug_field='name')
    user_group = UserGroupSerializer(slug_field='name')

    class Meta:
        model = PermissionMapper
        exclude = ['data_set']


class DataSetDetailSerializer(BaseSerializer):
    timeseries = TimeseriesRefSerializer(many=True, view_name='timeseries-detail', slug_field='uuid')
    owner = DataOwnerRefSerializer(slug_field='name')
    permission_mappers = PermissionMapperSerializer(read_only=True)

    class Meta:
        model = DataSet
        fields = ('id', 'url', 'name', 'owner', 'timeseries', 'permission_mappers')


class DataSetListSerializer(DataSetDetailSerializer):
    class Meta:
        model = DataSet
        fields = ('id', 'url', 'name', 'owner', )


class LogicalGroupParentRefSerializer(BaseSerializer):
    name = serializers.SerializerMethodField('get_name')
    parent_id = serializers.SerializerMethodField('get_parent_id')

    def get_name(self, obj):
        return obj.parent.name

    def get_parent_id(self, obj):
        return obj.parent.id

    class Meta:
        model = LogicalGroupEdge
        fields = ('id', 'parent', 'name', 'parent_id')

    # def field_to_native(self, obj, field):
    #     """
    #         return dict representation of model
    #     """
    #     return [{'url': t.parent, 'name': t.parent.name} for t in getattr(obj, field).all()]




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
        view_name='logicalgroup-detail', slug_field='id', read_only=True)

    class Meta:
        model = LogicalGroup
        fields = ('id', 'url', 'name', 'parents', 'owner')


class StatusCacheDetailSerializer(BaseSerializer):

    timeseries = TimeseriesSmallListSerializer()
    class Meta:
        model = StatusCache
        #exclude = ('timeseries', )


class StatusCacheListSerializer(StatusCacheDetailSerializer):

    timeseries = TimeseriesSmallListSerializer()
    class Meta:
        model = StatusCache
        #exclude = ('timeseries', )