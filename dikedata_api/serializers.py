# (c) Nelen & Schuurmans.  MIT licensed, see LICENSE.rst.

from __future__ import unicode_literals

from django.contrib.auth.models import Group as Role, User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.utils import simplejson as json

from rest_framework import serializers

from lizard_security.models import (
    DataOwner,
    DataSet,
    PermissionMapper,
    UserGroup,
)

from ddsc_core.models import (
    Alarm,
    Alarm_Active,
    Alarm_Item,
    Compartment,
    Location,
    LogicalGroup,
    LogicalGroupEdge,
    Manufacturer,
    MeasuringDevice,
    MeasuringMethod,
    Parameter,
    ProcessingMethod,
    ReferenceFrame,
    Source,
    StatusCache,
    Timeseries,
    Unit,
)

from ddsc_site.models import Annotation
from haystack.query import SearchQuerySet

from dikedata_api import fields


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
            return {
                'id': item.id,
                'code': item.code,
                'description': item.description
            }


class ParameterRelSerializer(AquoRelatedSerializer):

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


class UserGroupListSerializer(BaseSerializer):

    class Meta:
        model = UserGroup
        fields = ('id', 'url', 'name', )


class UserGroupDetailSerializer(BaseSerializer):

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
    owner = DataOwnerRefSerializer(slug_field='name')

    class Meta:
        model = Source
        fields = (
            'id', 'uuid', 'url', 'name', 'owner', 'source_type',
            'manufacturer', 'details', 'frequency', 'timeout'
            )


class SourceDetailSerializer(SourceListSerializer):

    class Meta:
        model = Source
        fields = (
            'id', 'uuid', 'url', 'name', 'owner', 'source_type',
            'manufacturer', 'details', 'frequency', 'timeout'
            )


class SourceRefSerializer(serializers.SlugRelatedField):

    class Meta:
        model = Source
        fields = (
            'uuid', 'url', 'name', 'owner', 'source_type', 'manufacturer'
            )

    def field_to_native(self, obj, field):
        item = getattr(obj, field)
        if item:
            return {'uuid': item.uuid, 'name': item.name}


class AlarmDetailSerializer(BaseSerializer):

    class Meta:
        model = Alarm
        #depth = 2


class ModelRefSerializer(serializers.SlugRelatedField):

    class Meta:
        model = ContentType


class AlarmSettingRefSerializer(serializers.SlugRelatedField):

    class Meta:
        model = Alarm


class ContentObjectSerializer(serializers.Field):

    def field_to_native(self, obj, field):
        item = getattr(obj, 'content_object')
        if item:
            return item.name
        else:
            return None


class AlarmItemDetailSerializer(BaseSerializer):
    comparision = fields.DictChoiceField(choices=Alarm_Item.COMPARISION_TYPE)
    logical_check = fields.DictChoiceField(choices=Alarm_Item.LOGIC_TYPES)
    value_type = fields.DictChoiceField(choices=Alarm_Item.VALUE_TYPE)
    alarm_type = ModelRefSerializer(slug_field='name')
    alarm = AlarmSettingRefSerializer(slug_field='id')
    content_object_name = ContentObjectSerializer()

    class Meta:
        model = Alarm_Item
        exclude = ('alarm', )
        #read_only_fields = ('content_object_name', )


class AlarmSettingDetailSerializer(BaseSerializer):
    alarm_item_set = AlarmItemDetailSerializer(many=True, read_only=True)
    frequency = fields.DictChoiceField(choices=Alarm.FREQUENCY_TYPE)
    urgency = fields.DictChoiceField(choices=Alarm.URGENCY_TYPE)
    logical_check = fields.DictChoiceField(choices=Alarm.LOGIC_TYPES)
    message_type = fields.DictChoiceField(choices=Alarm.MESSAGE_TYPE)

    class Meta:
        model = Alarm
        exclude = ('single_or_group', 'previous_alarm', )
        read_only_fields = (
            'date_cr',
            'first_born',
            'last_checked',
            'previous_alarm',
        )


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
    # two times a query to same object.. any way to optimize this?
    related_type = serializers.SerializerMethodField('get_type')
    related_uuid = serializers.SerializerMethodField('get_uuid')

    class Meta:
        model = Alarm_Active
        depth = 1

    def get_uuid(self, obj):
        alarm_item = obj.alarm.alarm_item_set.all()[0]
        if (alarm_item.alarm_type.name == 'timeseries' or
                alarm_item.alarm_type.name == 'location'):
            return alarm_item.content_object.uuid

    def get_type(self, obj):
        alarm_item = obj.alarm.alarm_item_set.all()[0]
        return alarm_item.alarm_type.name


class Alarm_ActiveListSerializer(Alarm_ActiveDetailSerializer):

    class Meta:
        model = Alarm_Active


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
    owner = DataOwnerRefSerializer(slug_field='name')
    #icon_url = serializers.SerializerMethodField('get_icon_url')

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
            'owner',
            'icon_url',
            'show_on_map',
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

    def get_icon_url(self, obj):
        # TODO: handle custom icon AND annotations...
        if obj.icon_url:
            # Custom icon
            return obj.icon_url
        else:
            # Default icon
            return "/app/images/marker-dam-3.png"

    def save_object(self, obj, **kwargs):
        obj.save_under(parent_pk=None)


class LocationListSerializer(LocationDetailSerializer):

    class Meta:
        model = Location
        fields = ('id',
                  'url',
                  'uuid',
                  'name',
                  'owner',
                  'icon_url',
                  'show_on_map',
                  'point_geometry',
                  'srid')

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
    annotations = serializers.SerializerMethodField('count_annotations')

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
            'annotations',
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
        read_only = (
            'id', 'uuid', 'first_value_timestamp', 'latest_value_timestamp',
            'latest_value',
            )

    def count_annotations(self, obj):
        sqs = SearchQuerySet().models(Annotation)
        sqs = sqs.filter(
            the_model_name__exact='timeseries',
            the_model_pk__exact=obj.pk
            )
        count = sqs.count()
        return count


class TimeseriesListSerializer(TimeseriesDetailSerializer):
    unit = serializers.SlugRelatedField(slug_field='code')
    parameter = serializers.SlugRelatedField(slug_field='code')
    annotations = serializers.SerializerMethodField('count_annotations')

    class Meta:
        model = Timeseries
        fields = (
            'id', 'url', 'uuid', 'name', 'location', 'latest_value_timestamp',
            'latest_value', 'events', 'value_type', 'parameter', 'unit',
            'annotations', 'owner', 'source'
            )
        depth = 2


class TimeseriesSmallListSerializer(TimeseriesDetailSerializer):
    unit = serializers.SlugRelatedField(slug_field='code')
    parameter = serializers.SlugRelatedField(slug_field='code')

    class Meta:
        model = Timeseries
        fields = (
            'id', 'url', 'uuid', 'name', 'parameter', 'latest_value',
            'value_type',
            )
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

        return [
            {'url': self.to_native(t), 'name': t.name}
            for t in getattr(obj, field).all()
        ]


class RecursiveTimeseriesSerializer(serializers.HyperlinkedRelatedField):

    class Meta:
        model = Timeseries

    def field_to_native(self, obj, field):
        #get display value

        return [
            {'url': self.to_native(t), 'name': t.name}
            for t in obj.timeseries_r()
        ]


class RoleSerializer(serializers.SlugRelatedField):

    class Meta:
        model = Role


class PermissionMapperSerializer(BaseSerializer):
    permission_group = serializers.PrimaryKeyRelatedField()
    user_group = serializers.PrimaryKeyRelatedField()
    data_set = serializers.HyperlinkedRelatedField(view_name='dataset-detail')

    class Meta:
        model = PermissionMapper
        exclude = ['data_set']

    def field_from_native(self, data, files, field_name, into):
        permission_mappers = []
        for pm_json in data.getlist('permission_mappers'):
            pm_data = json.loads(pm_json)
            if 'id' in pm_data:
                pm = PermissionMapper.objects.get(pk=pm_data['id'])
            else:
                pm = PermissionMapper()
            pm.permission_group = Role.objects.get(
                pk=pm_data['permission_group'])
            pm.user_group = UserGroup.objects.get(pk=pm_data['user_group'])
            permission_mappers.append(pm)
        into['permission_mappers'] = permission_mappers


class DataSetDetailSerializer(BaseSerializer):
    timeseries = TimeseriesRefSerializer(
        many=True, view_name='timeseries-detail', slug_field='uuid')
    owner = DataOwnerRefSerializer(slug_field='name')
    permission_mappers = PermissionMapperSerializer(many=True)

    class Meta:
        model = DataSet
        fields = (
            'id', 'url', 'name', 'owner', 'timeseries', 'permission_mappers'
            )


class DataSetListSerializer(DataSetDetailSerializer):

    class Meta:
        model = DataSet
        fields = ('id', 'url', 'name', 'owner', )


class LogicalGroupParentRefSerializer(BaseSerializer):
    name = serializers.SerializerMethodField('get_name')
    parent_id = serializers.SerializerMethodField('get_parent_id')

    class Meta:
        model = LogicalGroupEdge
        fields = ('id', 'parent', 'name', 'parent_id')

    def get_name(self, obj):
        return obj.parent.name

    def get_parent_id(self, obj):
        return obj.parent.id


class LogicalGroupDetailSerializer(BaseSerializer):
    id = serializers.Field('id')
    timeseries = TimeseriesRefSerializer(
        many=True, view_name='timeseries-detail', slug_field='uuid')
    parents = LogicalGroupParentRefSerializer(many=True, read_only=True)
    childs = fields.ManyHyperlinkedChilds(
        view_name='logicalgroup-detail', read_only=True)
    owner = DataOwnerRefSerializer(slug_field='name')

    class Meta:
        model = LogicalGroup


class LogicalGroupListSerializer(LogicalGroupDetailSerializer):
    parents = fields.ManyHyperlinkedParents(
        many=True, view_name='logicalgroup-detail', slug_field='id',
        read_only=True)

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
