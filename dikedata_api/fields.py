# (c) Nelen & Schuurmans.  MIT licensed, see LICENSE.rst.
from __future__ import unicode_literals

from rest_framework import fields, serializers
from rest_framework.reverse import reverse
from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry, Point

COLNAME_FORMAT_MS = '%Y-%m-%dT%H:%M:%S.%fZ' # supports milliseconds


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
                return reverse('event-detail', args=[obj.uuid, latest_value],
                    request=self.context['request'])
            return None
        return obj.latest_value()


class OpenDAPLink(serializers.HyperlinkedIdentityField):
    def field_to_native(self, obj, field_name):
        opendap_url = getattr(settings, 'OPENDAP_BASE_URL', '')
        request = self.context.get('request', None)
        format = request.QUERY_PARAMS.get('format', None)

        format_map = {
            'api': 'html',
            'json': 'ascii',
        }
        if format in format_map:
            opendap_format = format_map[format]
        else:
            opendap_format = 'html'
        return "%s/%s.%s" % (opendap_url, obj.uuid, opendap_format)


class DictChoiceField(serializers.ChoiceField):
    def to_native(self, value):
        #get display value
        choices_dict = dict(self._choices)
        return choices_dict[value]

    def from_native(self, value):
        #get value from display value (assuming that display values are unique)
        choices_dict = dict([(a[1],a[0]) for a in self._choices])
        print choices_dict[value]
        return choices_dict[value]


class GeometryPointField(serializers.Field):

    def field_from_native(self, data, files, field_name, into):
        """
        get geometry object
        """
        value = data.getlist(field_name, None)
        print '------------------------------'
        print value
        srid = int(data.get('srid', 4258))
        if value and len(value) > 0:
            if len(value) < 2:
                value = value[0].split(',')
            values = [float(v) for v in value]
            geo_input = Point(*values, srid=srid)
            if srid != 4258:
                geo_input_clone = geo_input.transform(4258, clone=True)
            into[field_name] = geo_input
        return geo_input
