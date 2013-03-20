# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.txt.
"""
Provides middleware that sets the user groups we're a member of (based on
Django users) and that sets the data sets we have access to through the
permission mapper mechanism.

"""
from django.db import models
from django.contrib.auth import authenticate
from django.contrib.auth import login as django_login
from django.contrib.auth.models import User
from django.utils import timezone


class AuthenticationMiddleware(object):
    def process_request(self, request):
        username = request.META.get('HTTP_USERNAME', None)
        password = request.META.get('HTTP_PASSWORD', None)

        if username and password:
            del request.META['HTTP_USERNAME']
            del request.META['HTTP_PASSWORD']
            try:
                user = authenticate(username=username, password=password)
                django_login(request, user)
                request._dont_enforce_csrf_checks = True
            except Exception as ex:
                setattr(request, 'AUTHENTICATION_EXCEPTION', ex)
