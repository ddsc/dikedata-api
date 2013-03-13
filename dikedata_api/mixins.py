# (c) Nelen & Schuurmans.  MIT licensed, see LICENSE.rst.
from __future__ import unicode_literals

from django.contrib.auth.decorators import permission_required
from django.utils.decorators import method_decorator
from rest_framework import generics, mixins
from rest_framework.renderers import BrowsableAPIRenderer, JSONRenderer

from dikedata_api.exceptions import APIException


class BaseMixin(object):
    def initial(self, request, *args, **kwargs):
        if hasattr(request, 'AUTHENTICATION_EXCEPTION'):
            raise getattr(request, 'AUTHENTICATION_EXCEPTION')
        return super(BaseMixin, self).initial(request, *args, **kwargs)

    def handle_exception(self, exc):
        wrapped = APIException(exc)
        return super(BaseMixin, self).handle_exception(wrapped)


class GetListModelMixin(mixins.ListModelMixin):
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class PostListModelMixin(mixins.CreateModelMixin):
    @method_decorator(permission_required('add', raise_exception=True))
    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)


class ProtectedListModelMixin(mixins.ListModelMixin, mixins.CreateModelMixin):
    @method_decorator(permission_required('staff', raise_exception=True))
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    @method_decorator(permission_required('staff', raise_exception=True))
    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)


class DetailModelMixin(mixins.RetrieveModelMixin,
                       mixins.UpdateModelMixin,
                       mixins.DestroyModelMixin):
    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    @method_decorator(permission_required('change', raise_exception=True))
    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    @method_decorator(permission_required('delete', raise_exception=True))
    def delete(self, request, *args, **kwargs):
        return self.destroy(request, *args, **kwargs)


class ProtectedDetailModelMixin(mixins.RetrieveModelMixin,
                                mixins.UpdateModelMixin,
                                mixins.DestroyModelMixin):
    @method_decorator(permission_required('staff', raise_exception=True))
    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    @method_decorator(permission_required('staff', raise_exception=True))
    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    @method_decorator(permission_required('staff', raise_exception=True))
    def delete(self, request, *args, **kwargs):
        return self.destroy(request, *args, **kwargs)
