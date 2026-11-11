# Gazeta — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
"""Synthetic fixtures: temp git repos with controlled times, and a fake work-map CLI."""
import json
import os
import subprocess
import sys
import tempfile
import time

ENGINE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plugin", "engine")
if ENGINE not in sys.path:
    sys.path.insert(0, ENGINE)

NOW = 1_800_000_000  # the injected clock
DAY = 86400


def git(repo, *args, when=None):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@t", GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null")
    if when is not None:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = "%d +0000" % when
    done = subprocess.run(("git", "-C", repo) + args, capture_output=True, text=True, env=env)
    assert done.returncode == 0, done.stderr
    return done.stdout


def make_repo(root, name="repo"):
    repo = os.path.join(root, name)
    os.makedirs(repo)
    git(repo, "init", "-q", "-b", "main")
    return repo


def write(repo, rel, text, mtime=None):
    path = os.path.join(repo, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def commit(repo, message, when, *paths):
    git(repo, "add", "-A", *(paths or (".",)))
    git(repo, "commit", "-q", "-m", message, when=when)


class Tmp:
    """Context-free temp dir for unittest setUp/tearDown."""
    def __init__(self):
        self._dir = tempfile.TemporaryDirectory()
        self.path = os.path.realpath(self._dir.name)

    def close(self):
        self._dir.cleanup()


FAKE_WORK_MAP = r'''
import json, sys
args = sys.argv[1:]
cfg = json.load(open(args[args.index("--config") + 1]))
rest = [a for i, a in enumerate(args) if a != "--json" and a != "--config" and (i == 0 or args[i - 1] != "--config")]
cmd, recs = rest[0], cfg["records"]
if cmd == "query":
    print(json.dumps(recs))
elif cmd == "slice":
    proj = rest[rest.index("--project") + 1]
    print(json.dumps([r for r in recs if r["project"] == proj and r["kind"] != "ship"]))
else:
    sys.exit(2)
'''


def rec(kind, id_, project, status="live", date="", gist="", source=("PIPELINE.md", 1), links=None):
    return {"kind": kind, "id": id_, "project": project, "session": "s", "status": status, "date": date,
            "gist": gist, "source": {"file": source[0], "line": source[1]}, "links": links or {}}


def fake_work_map(root, records, pipeline_files=(), map_text=""):
    """Write the fake CLI plus its config; return (script, config)."""
    script = os.path.join(root, "fake_work_map.py")
    with open(script, "w") as fh:
        fh.write(FAKE_WORK_MAP)
    with open(os.path.join(root, "PIPELINE.md"), "w") as fh:
        fh.write(map_text)
    config = os.path.join(root, "work-map.json")
    with open(config, "w") as fh:
        json.dump({"records": records, "pipeline": list(pipeline_files)}, fh)
    return script, config
