
from collections import OrderedDict
from io import StringIO
import re
from bossman.repo import Revision


class GenericVersionComments:
  @staticmethod
  def from_revision(revision: Revision):
    comments = StringIO()
    comments.write(revision.message.strip())
    comments.write("\n\n")
    comments.write("commit: {}\n".format(revision.id))
    comments.write("branch: {}\n".format(", ".join(revision.branches)))
    comments.write("author: {} <{}>\n".format(revision.author_name, revision.author_email))
    if revision.author_email != revision.committer_email:
      comments.write("committer: {} <{}>\n".format(revision.commit.committer.name, revision.commit.committer.email))
    return GenericVersionComments(comments.getvalue())

  def __init__(self, comments: str):
    parts = comments.strip().rsplit("\n\n", 1)
    self.message = parts[0]
    self.metadata = (OrderedDict(re.findall(r"^([^:]+):\s*(.*)$", parts[1], re.MULTILINE))
      if len(parts) == 2
      else {})

  def __str__(self) -> str:
    return "{}\n\n{}".format(
      self.message,
      "\n".join(
        "{}: {}".format(k, v)
        for k, v in self.metadata.items()
      )
    )

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
