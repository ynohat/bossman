from .repo import Repo
import packaging.version
from rich.console import Console
from git import GitConfigParser

def __0_25_1(conf: GitConfigParser, repo: Repo, console: Console):
  """
  Until v0.25.1 inclusive, bossman init changed the git config to add explicit push/fetch
  refspecs to force git pull/push to also fetch/push notes.

  This behaviour was changed in favour of an explicit pull and push as part of application
  logic when relevant (e.g. before bossman status/prerelease/release, before an after bossman apply).

  The change was largely motivated by the fact that adding the fetch/push refspecs to the config
  appears to break normal branch tracking, forcing an explicit `git push origin ref`, not great UX.
  Because notes are critical to bossman, it's also better not to rely on the user remembering to push
  after apply.
  """
  notes_refspec = "+refs/notes/*:refs/notes/*"
  for section in conf.sections():
    if section.startswith("remote"):
      push_refspecs = conf.get_values(section, "push", [])
      if notes_refspec in push_refspecs:
        conf.remove_option(section, "push")
        push_refspecs = list(refspec for refspec in push_refspecs if refspec != notes_refspec)
        for refspec in push_refspecs:
          conf.add_value(section, "push", refspec)
        console.print(r"[red]-[/] \[{}] push: {}".format(section, notes_refspec))
      fetch_refspecs = conf.get_values(section, "fetch", [])
      if notes_refspec in fetch_refspecs:
        conf.remove_option(section, "fetch")
        fetch_refspecs = list(refspec for refspec in fetch_refspecs if refspec != notes_refspec)
        for refspec in fetch_refspecs:
          conf.add_value(section, "fetch", refspec)
        console.print(r"[red]-[/] \[{}] fetch: {}".format(section, notes_refspec))

MIGRATIONS = {
  "0.25.1": __0_25_1
}

def required(conf: GitConfigParser):
  parse = packaging.version.parse
  conf_version = parse(conf.get_value("bossman", "version", "0.0.0"))
  return any(conf_version <= parse(version) for version in MIGRATIONS)

def migrate(conf: GitConfigParser, repo: Repo, console: Console):
  if "bossman" not in conf.sections():
    conf.add_section("bossman")
  console.print("Initializing git configuration [yellow]{}[/]...".format(conf._file_or_files))
  conf_version = packaging.version.parse(conf.get_value("bossman", "version", "0.0.0"))
  for version, migration in MIGRATIONS.items():
    if conf_version <= packaging.version.parse(version):
      migration(conf, repo, console)