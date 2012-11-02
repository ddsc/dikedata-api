# (c) Nelen & Schuurmans.  MIT licensed, see LICENSE.rst.
from __future__ import unicode_literals

from datetime import datetime
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.http import HttpResponse
from django.utils import simplejson as json
from django.utils.translation import ugettext as _
from lizard_ui.views import UiView
from cassandralib.models import CassandraDataStore
from rabbitmqlib.models import Producer

import pandas as pd
import pytz
import uuid


SERVERS = settings.CASSANDRA['servers']
KEYSPACE = settings.CASSANDRA['keyspace']
COL_FAM = settings.CASSANDRA['column_family']
COLNAME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
INTERNAL_TIMEZONE = pytz.UTC

def api_response(request):
    cassandra = CassandraDataStore(SERVERS, KEYSPACE, COL_FAM, 10000)
    
    msg = {}
    get = request.GET.keys()
    try:
        if not 'request' in get:
            raise Exception("Missing GET parameter 'request'")
        params = json.loads(request.GET.get('request'))
        if not 'observers' in params:
            raise Exception("Missing parameter 'observers'")
        msg['observers'] = {}
        if 'start' in params:
            start = datetime.strptime(params['start'], COLNAME_FORMAT)
        else:
            start = datetime.now() + relativedelta( years = -3 )
        if 'end' in params:
            end = datetime.strptime(params['end'], COLNAME_FORMAT)
        else:
            end = datetime.now()
        for observer_id in params['observers']:
            filter = ['value', 'flag']
    
            df = cassandra.read(observer_id,
                INTERNAL_TIMEZONE.localize(start),
                INTERNAL_TIMEZONE.localize(end), params=filter)
            
            data = [
                dict([('datetime', timestamp.strftime(COLNAME_FORMAT))] + [
                    (colname, row[i])
                    for i, colname in enumerate(df.columns)
                ])
                for timestamp, row in df.iterrows()
            ]
            msg['observers'][observer_id] = data

    except Exception as ex:
        msg['status'] = ex.__class__.__name__
        msg['errors'] = ex.args

    return HttpResponse(json.dumps(msg, indent=4), mimetype='application/json')

def api_write(request):
    msg = {}
    get = request.GET.keys()
    try:
        if not 'request' in get:
            raise Exception("Missing GET parameter 'request'")
        params = json.loads(request.GET.get('request'))
        if not 'observers' in params:
            raise Exception("Missing parameter 'observers'")
        observers = params['observers']
        msg = {'observers': observers}

        # Store time series in Cassandra
        for obs_id in observers:
            datetimes = []
            data = []
            for datum in observers[obs_id]:
                if "datetime" in datum:
                    dt = datetime.strptime(datum["datetime"], COLNAME_FORMAT)
                    datetimes.append(dt.replace(tzinfo=INTERNAL_TIMEZONE))
                    del datum["datetime"]
                    data.append(datum)
            df = pd.DataFrame(data=data, index=datetimes)
            cassandra = CassandraDataStore(
                settings.CASSANDRA['servers'],
                settings.CASSANDRA['keyspace'],
                settings.CASSANDRA['column_family'],
                10000
            )
            cassandra.write(obs_id, df)

        # Inform Rabbit MQ
        msg['message_id'] = str(uuid.uuid4())
        producer = Producer(settings.RABBITMQ['server'],
            settings.RABBITMQ['user'], settings.RABBITMQ['password'],
            settings.RABBITMQ['vhost'])
        producer.send(msg, b"timeseries", b"store")
        msg['status'] = 'OK'
    except Exception as ex:
        msg['status'] = ex.__class__.__name__
        msg['errors'] = ex.args

    return HttpResponse(json.dumps(msg, indent=4), mimetype='application/json')
