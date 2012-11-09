# (c) Nelen & Schuurmans.  MIT licensed, see LICENSE.rst.
from __future__ import unicode_literals

from cassandralib.models import CassandraDataStore
from datetime import datetime
from dateutil.relativedelta import relativedelta
from django.conf import settings

import pandas as pd
import pytz
import uuid


SERVERS = settings.CASSANDRA['servers']
KEYSPACE = settings.CASSANDRA['keyspace']
COL_FAM = settings.CASSANDRA['column_family']
COLNAME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
INTERNAL_TIMEZONE = pytz.UTC

class ObserverManager:
    cassandra = CassandraDataStore(SERVERS, KEYSPACE, COL_FAM, 10000)

    def all(self):
        return [
            Observer("3201.NEERSG.accumulative"),
            Observer("3201.VERDPG.accumulative"),
            Observer("3201_PS3.Q.instantaneous"),
        ]

    def filter(self, pk, params = {}):
        if 'start' in params:
            start = datetime.strptime(params['start'], COLNAME_FORMAT)
        else:
            start = datetime.now() + relativedelta( years = -3 )
        if 'end' in params:
            end = datetime.strptime(params['end'], COLNAME_FORMAT)
        else:
            end = datetime.now()
        filter = ['value', 'flag']

        df = self.cassandra.read(pk,
            INTERNAL_TIMEZONE.localize(start),
            INTERNAL_TIMEZONE.localize(end), params=filter)
        
        data = [
            dict([('datetime', timestamp.strftime(COLNAME_FORMAT))] + [
                (colname, row[i])
                for i, colname in enumerate(df.columns)
            ])
            for timestamp, row in df.iterrows()
        ]
        return Observer(pk, data)

class Observer:
    objects = ObserverManager()

    id = None
    data = None
    
    @property
    def url(self):
        return "/api/observers/%s" % self.id

    def __init__(self, id, data=[]):
        self.id = id
        self.data = data



