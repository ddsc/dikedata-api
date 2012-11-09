# (c) Nelen & Schuurmans.  MIT licensed, see LICENSE.rst.
from __future__ import unicode_literals

from dikedata_api.models import Observer
from rest_framework import serializers


class ObserverSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Observer
        fields = ('id')
