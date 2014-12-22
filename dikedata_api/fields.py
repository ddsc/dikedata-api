# (c) Nelen & Schuurmans.  MIT licensed, see LICENSE.rst.
from __future__ import unicode_literals

import math

from django.conf import settings
from django.contrib.gis.geos import Point
from rest_framework import fields, serializers
from rest_framework.reverse import reverse

from ddsc_core.utils import transform

COLNAME_FORMAT_MS = '%Y-%m-%dT%H:%M:%S.%fZ'  # supports milliseconds


class AquoField(fields.Field):
    class Meta:
        fields = ('id', 'code', 'description')

    def to_native(self, obj):
        return dict([(k, getattr(obj, k, None)) for k in self.Meta.fields])


class DateTimeField(fields.Field):
    def field_to_native(self, obj, field_name):
        field = getattr(obj, field_name, None)
        if field:
            return field.strftime(COLNAME_FORMAT_MS)


class RelatedField(serializers.ModelField):
    def field_to_native(self, obj, field_name):
        relation = getattr(obj, field_name)
        return getattr(relation, self.model_field, None)


class ManyRelatedField(serializers.ModelField):
    def field_to_native(self, obj, field_name):
        manager = getattr(obj, field_name)
        return [getattr(rel, self.model_field, None) for rel in manager.all()]


class HyperlinkedRelatedMethod(serializers.HyperlinkedRelatedField):
    def field_to_native(self, obj, field_name):
        method = getattr(obj, field_name)
        try:
            return self.to_native(method())
        except:
            pass


class ManyHyperlinkedRelatedMethod(serializers.HyperlinkedRelatedField):
    def field_to_native(self, obj, field_name):
        method = getattr(obj, field_name)
        try:
            return [self.to_native(item) for item in method()]
        except:
            pass


class ManyHyperlinkedParents(serializers.HyperlinkedRelatedField):
    def field_to_native(self, obj, field_name):
        manager = getattr(obj, field_name)
        return [self.to_native(item.parent) for item in manager.all()]


class ManyHyperlinkedChilds(serializers.HyperlinkedRelatedField):
    def field_to_native(self, obj, field_name):
        manager = getattr(obj, field_name)
        return [self.to_native(item.child) for item in manager.all()]


class LatestValue(serializers.HyperlinkedIdentityField):

    def field_to_native(self, obj, field_name):

        if obj.is_file():
            latest_value = obj.latest_value_file()
            if latest_value:
                return reverse(
                    'event-detail', args=[obj.uuid, latest_value],
                    request=self.context['request'])
            return None

        # Not a number, float("NaN"), is serialized to NaN (without quotes),
        # which is not valid JSON. None, on the other hand, is serialized
        # to null (without quotes), which is valid JSON and does not
        # choke client-side parsers.

        latest_value = obj.latest_value()
        if isinstance(latest_value, float) and math.isnan(latest_value):
            return None
        else:
            return latest_value


class OpenDAPLink(serializers.Field):
    def field_to_native(self, obj, field_name):
        opendap_url = getattr(settings, 'OPENDAP_BASE_URL', '')
        opendap_format = 'ascii'
        return "%s/%s.%s" % (opendap_url, obj.uuid, opendap_format)


class DictChoiceField(serializers.ChoiceField):
    def to_native(self, value):
        #get display value
        choices_dict = dict(self._choices)
        if value in choices_dict:
            return choices_dict[value]
        else:
            return 'unknown choice (%s)' % str(value)

    def from_native(self, value):
        #get value from display value (assuming that display values are unique)
        choices_dict = dict([(a[1], a[0]) for a in self._choices])
        return choices_dict[value]


class GeometryPointField(serializers.Field):

    def field_from_native(self, data, files, field_name, into):
        """
        get geometry object
        """
        value = data.getlist(field_name, None)
        srid = int(data.get('srid', 4258))
        if value and len(value) > 0 and len(value[0]) > 0:
            if len(value) < 2:
                value = value[0].split(',')
            values = [float(v) for v in value]
            geo_input = Point(*values, srid=srid)
            if srid != 4258:
                geo_input = transform(geo_input, 4258, clone=True)
            into[field_name] = geo_input
            return geo_input
        else:
            return ''
