# (c) Nelen & Schuurmans.  MIT licensed, see LICENSE.rst.
from __future__ import unicode_literals

from rest_framework.parsers import BaseParser, DataAndFiles


class SimpleFileUploadParser(BaseParser):
    """
    A naive raw file upload parser.
    """
    media_type = '*/*'  # Accept anything

    def parse(self, stream, media_type=None, parser_context=None):
        content = stream.read()

        return DataAndFiles({}, content)


class CSVParser(BaseParser):

    media_type = 'text/csv'

    def parse(self, stream, media_type=None, parser_context=None):
        content = [line.strip().split(';') \
            for line in stream.read().split('\n') if line.strip()]

        data = [{'uuid':row[1].strip('"'),
                 'events':[{'datetime':row[0].strip('"'),
                            'value':row[2].strip('"')}]}
                for row in content]
        
        return DataAndFiles(data, None)
