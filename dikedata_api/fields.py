# (c) Nelen & Schuurmans.  MIT licensed, see LICENSE.rst.
from __future__ import unicode_literals

from rest_framework import fields, serializers
from rest_framework.reverse import reverse

COLNAME_FORMAT_MS = '%Y-%m-%dT%H:%M:%S.%fZ' # supports milliseconds


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
