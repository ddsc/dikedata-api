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

import pytz
import uuid


def api_response(request):
    SERVERS = settings.CASSANDRA['servers']
    KEYSPACE = settings.CASSANDRA['keyspace']
    COL_FAM = settings.CASSANDRA['column_family']
    COLNAME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
    INTERNAL_TIMEZONE = pytz.UTC
    
    cassandra = CassandraDataStore(SERVERS, KEYSPACE, COL_FAM, 10000)
    
    out = {}
    get = request.GET.keys()
    try:
        if 'request' in get:
            params = json.loads(request.GET.get('request'))
            if 'start' in params:
                start = datetime.strptime(params['start'], COLNAME_FORMAT)
            else:
                start = datetime.now() + relativedelta( years = -3 )
            if 'end' in params:
                end = datetime.strptime(params['end'], COLNAME_FORMAT)
            else:
                end = datetime.now()
            if "observers" in params:
                out['observers'] = {}
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
                    out['observers'][observer_id] = data

    except Exception as ex:
        out['errors'] = ex.arg

    return HttpResponse(json.dumps(out, indent=4), mimetype='application/json')

def api_write(request):
    out = {}
    get = request.GET.keys()
    try:
        if 'request' in get:
            params = json.loads(request.GET.get('request'))
            if 'observers' in params:
                observers = params['observers']
                producer = Producer(settings.RABBITMQ['server'],
                    settings.RABBITMQ['user'], settings.RABBITMQ['password'],
                    settings.RABBITMQ['vhost'])
                msg_id = uuid.uuid4()
                out = {'message_id': str(msg_id), 'observers': observers}
                producer.send(out, b"timeseries", b"store")
                out['status'] = 'sent'
    except Exception as ex:
        out['errors'] = ex.args

    return HttpResponse(json.dumps(out, indent=4), mimetype='application/json')
