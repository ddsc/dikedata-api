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
