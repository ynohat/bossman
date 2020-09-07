import logging

_console_formatter = logging.Formatter("%(message)s")

_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_console_formatter)

logger = logging.getLogger()

def get_class_logger(instance):
  return logger.getChild(
    "{module_name}.{class_name}".format(
      module_name=instance.__class__.__module__,
      class_name=instance.__class__.__name__
    )
  )