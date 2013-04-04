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
    'ParseError':            (400,  10, "Incorrect request format."),
    'ValidationError':       (400,  20, "Incomplete request content."),
    'NotAuthenticated':      (401,  10, "Not authenticated"),
    'AuthenticationFailed':  (401,  20, "Authentication failed."),
    'AutheticationFailed':   (401,  21, "Authentication failed."),
    'PermissionDenied':      (403,  10, "Permission denied."),
    'Http404':               (404,  10, "Resource not found."),
    'DoesNotExist':          (404,  11, "Resource not found."),
    'MethodNotAllowed':      (405,  10, "Request method not available."),
    # Technical problems
    'Exception':             (500,   0, "Unknown technical error."),
    'NameError':             (500,  10, "Technical error"),
    'TypeError':             (500,  11, "Technical error."),
    'UnboundLocalError':     (500,  12, "Technical error."),
    'DatabaseError':         (500,  20, "Database error."),
    'FieldError':            (500,  21, "Database error."),
    'IOError':               (500,  30, "Disk error."),
    'AllServersUnavailable': (502,  10, "External server unavailable."),
    'MaximumRetryException': (502,  20, "External server error"),
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
            if len(trace) > 0:
                (file, line, method, expr) = trace[-1]
            else:
                (file, line, method, expr) = ("", 0, "", "")
            msg = '%s: %s in %s, line %d' % (
                ex.__class__.__name__,
                ', '.join(str(x) for x in ex.args),
                file,
                line
            )
            if self.status_code < 500:
                logger.debug('%s - %s' % (self.detail, msg))
            else:
                logger.exception(self.detail)
