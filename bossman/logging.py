import logging
import sys

import requests

import textwrap
class _Formatter(logging.Formatter):
  def formatRequestsMessage(self, record):
    _formatHeaders = lambda d: '\n'.join(f'{k}: {v}' for k, v in d.items())
    return textwrap.dedent('''
      ---------------- request ----------------
      {req.method} {req.url}
      {reqhdrs}
      {req.body}
      ---------------- response ----------------
      {res.status_code} {res.reason} {res.url}
      {reshdrs}
      {res.text}
    ''').format(
      req=record.req,
      res=record.res,
      reqhdrs=_formatHeaders(record.req.headers),
      reshdrs=_formatHeaders(record.res.headers),
    )

  def formatMessage(self, record):
    result = super().formatMessage(record)
    if record.name == 'requests':
      result += self.formatRequestsMessage(record)
    return result

_formatter = _Formatter('{asctime} {levelname} {name} {message}', style='{')

_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_formatter)
_console_handler.setStream(sys.stderr)

logger = logging.getLogger()
logger.addHandler(_console_handler)

def get_class_logger(instance):
  return logger.getChild(
    "{module_name}.{class_name}".format(
      module_name=instance.__class__.__module__,
      class_name=instance.__class__.__name__
    )
  )

class RequestsLoggingSession(requests.Session):
  def __init__(self, *args, **kwargs):
    super(RequestsLoggingSession, self).__init__(*args, **kwargs)
    self.logger = logger.getChild('requests')
    self.logger.propagate = True
    self.hooks['response'].append(self.logRoundtrip)

  def logRoundtrip(self, response, *args, **kwargs):
    extra = {'req': response.request, 'res': response}
    self.logger.debug('HTTP roundtrip', extra=extra)
