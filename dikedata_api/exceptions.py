# (c) Nelen & Schuurmans.  MIT licensed, see LICENSE.rst.
from __future__ import unicode_literals

from django.conf import settings
from rest_framework.exceptions import APIException as BaseException

import logging
import sys
import traceback


logger = logging.getLogger(__name__)

EXCEPTION_MAP = {
    #                        HTTP CODE  DESCRIPTION
    #                        ==== ===== ===========
    # Interface problems
    'ValueError':            (200,  10, "Incorrect parameter value format."),
    # Functional problems
    'Http404':               (404,  10, "Resource not found."),
    # Technical problems
    'Exception':             (500,  10, "Unknown technical error."),
    'AllServersUnavailable': (502,  10, "External server unavailable."),
}

class APIException(BaseException):
    status_code = None
    detail = None

    def __init__(self, ex):
        ex_name = ex.__class__.__name__
        if ex_name not in EXCEPTION_MAP:
            ex_name = 'Exception'
        self.status_code, error, desc = EXCEPTION_MAP[ex_name]
        self.detail = '%d-%d: %s' % (self.status_code, error, desc)
        if ex:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            trace = traceback.extract_tb(exc_traceback)
            (file, line, method, expr) = trace[-1]
            msg = '%s: %s in %s, line %d' % (
                ex.__class__.__name__,
                ', '.join(ex.args),
                file,
                line
            )
            if self.status_code < 500:
                logger.debug('%s - %s' % (self.detail, msg))
            else:
                logger.error('%s - %s' % (self.detail, msg))
