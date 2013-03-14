# (c) Nelen & Schuurmans.  MIT licensed, see LICENSE.rst.
from __future__ import unicode_literals

from django.http.multipartparser import parse_header
from rest_framework.renderers import BaseRenderer

COLNAME_FORMAT = '%Y-%m-%d %H:%M:%S.%f'


class CSVRenderer(BaseRenderer):
    """
    Renderer which serializes to csv.
    """

    media_type = 'text/csv'
    format = 'csv'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        """
        Render `obj` into csv.
        """
        if data is None:
            return ''

        response = '"datetime (utc)";' + \
            ';'.join(['"%s"' % column for column in data.columns]) + '\n' + \
            ''.join(['%s\n' % row for row in \
                ['"%s";' % timestamp.strftime(COLNAME_FORMAT) + \
                ';'.join(['"%s"' % row[i] for i, _ in enumerate(data.columns)])
                for timestamp, row in data.iterrows()]])

        return response
