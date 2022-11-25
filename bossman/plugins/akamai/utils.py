
from collections import OrderedDict
from io import StringIO
from copy import deepcopy
import re
from bossman.repo import Revision
from bossman.errors import BossmanError


class GenericVersionComments:
  @staticmethod
  def from_revision(revision: Revision, truncate_to: int = None):
    comments = StringIO()
    comments.write(revision.message.strip())
    comments.write("\n\n")
    comments.write("commit: {}\n".format(revision.id))
    comments.write("branch: {}\n".format(", ".join(revision.branches)))
    comments.write("author: {} <{}>\n".format(revision.author_name, revision.author_email))
    if revision.author_email != revision.committer_email:
      comments.write("committer: {} <{}>\n".format(revision.commit.committer.name, revision.commit.committer.email))
    return GenericVersionComments(comments.getvalue(), truncate_to)

  def __init__(self, comments: str, truncate_to: int = None):
    self.truncate_to = truncate_to
    parts = comments.strip().rsplit("\n\n", 1)
    self.message = parts[0]
    self.metadata = (OrderedDict(re.findall(r"^([^:]+):\s*(.*)$", parts[1], re.MULTILINE))
      if len(parts) == 2
      else {})

  def __str__(self):
    def _format(msg, metadata):
      return "{}\n\n{}".format(
        msg,
        "\n".join(
          "{}: {}".format(k, v)
          for k, v in metadata.items()
        )
      )

    def _shorten(msg: str, metadata):
      """
      Yield successively shorter versions of the message.
      """
      # try the full message first
      yield _format(msg, metadata)

      # if too long, try truncating the commit message GitHub style
      msg = msg.split('\n', 1)[0][:80]
      yield _format(msg, metadata)

      # if too long, remove non-essential metadata
      for key in sorted(metadata.keys()):
        if key != 'commit':
          metadata.pop(key)
          yield _format(msg, metadata)

    for s in _shorten(self.message, deepcopy(self.metadata)):
      if self.truncate_to == None or len(s) <= self.truncate_to:
        return s

    # we should NEVER see this
    raise BossmanError("Failed to truncate the description message to the required length {}".format(self.truncate_to))

  @property
  def commit(self):
    return self.metadata.get("commit", None)

  @property
  def subject_line(self):
    # 72 chars matches GitHub guidance, but it's a bit long for the console
    return self.message.split("\n")[0][:40]

  @property
  def branch(self):
    return self.metadata.get("branch", None)

  @property
  def author(self):
    return self.metadata.get("author", None)

  @property
  def committer(self):
    return self.metadata.get("committer", None)
