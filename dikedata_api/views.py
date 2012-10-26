# (c) Nelen & Schuurmans.  MIT licensed, see LICENSE.rst.
from __future__ import unicode_literals

from datetime import datetime
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.http import HttpResponse
from django.utils import simplejson
from django.utils.translation import ugettext as _
from lizard_ui.views import UiView
from models import CassandraDataStore
from models import RabbitMQ

import pytz


def api_response(request):
    SERVERS = settings.CASSANDRA['servers']
    KEYSPACE = settings.CASSANDRA['keyspace']
    COL_FAM = settings.CASSANDRA['column_family']
    COLNAME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
    tz = pytz.UTC
    
    reader = CassandraDataStore(SERVERS, KEYSPACE, COL_FAM, 10000)
    
    out = {}
    print request
    params = request.GET.keys()
    try:
        if 'observer' in params:
            observer_id = request.GET.get('observer')
            if 'start' in params:
                start = datetime.strptime(request.GET.get('start'), COLNAME_FORMAT)
            else:
                start = datetime.now() + relativedelta( years = -3 )
            if 'end' in params:
                end = datetime.strptime(request.GET.get('end'), COLNAME_FORMAT)
            else:
                end = datetime.now()
            filter = ['value', 'flag']
    
            df = reader.read(observer_id, tz.localize(start), tz.localize(end),
                             params=filter)
            
            data = [
                dict([('datetime', timestamp)] + [
                    (colname, row[i])
                    for i, colname in enumerate(df.columns)
                ])
                for timestamp, row in df.iterrows()
            ]
            out['observers'] = [{'id': observer_id, 'data': data}]

    except Exception as ex:
        out['errors'] = ex.arg


    return HttpResponse(simplejson.dumps(out, indent=4),
                        mimetype='application/json')

def api_write(request):
    out = {}
    params = request.GET.keys()
    try:
        if 'observer' in params:
            observer_id = request.GET.get('observer')
            rabbit = RabbitMQ(settings.RABBITMQ['server'],
                settings.RABBITMQ['user'], settings.RABBITMQ['password'],
                settings.RABBITMQ['vhost'])
            dummy = [{"datetime": "2009-03-26T23:00:00Z", "value": "37"},
                     {"datetime": "2009-03-27T23:00:00Z", "value": "42"}]
            msg = [{'id': observer_id, 'data': dummy}]
            rabbit.send(msg, b"timeseries", b"store")
            out['observers'] = msg
    except Exception as ex:
        out['errors'] = ex.arg


    return HttpResponse(simplejson.dumps(out, indent=4),
                        mimetype='application/json')
