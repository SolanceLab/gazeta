# Gazeta — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
"""When was a project last touched? The newest of four signals: commit, uncommitted, decision, pipeline.

Records-only commits, reformats and noise (caches, logs) do not count. Plans and specs do.
"""
import fnmatch
import os
import re
import subprocess
import time
from collections import namedtuple

Signal = namedtuple("Signal", "kind time")

NOISE_DIRS = ("__pycache__", "node_modules")
NOISE_PREFIXES = (".claude/worktrees/",)
RECORDS = ("DECISIONS*.md", "DEVLOG.md", "PIPELINE.md", "MAP.md", "SYSTEM-MAP.md", "CHANGELOG.md")
NOISE_FILES = ("*.pyc", ".DS_Store", "*.log")
GIT_TIMEOUT = 10


def _git(cwd, *args):
    try:
        done = subprocess.run(("git", "-C", cwd) + args, capture_output=True, text=True, timeout=GIT_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout if done.returncode == 0 else None


def is_record(path):
    return any(fnmatch.fnmatch(os.path.basename(path), pat) for pat in RECORDS)


def is_noise(path):
    parts = path.replace(os.sep, "/").split("/")
    if any(p in NOISE_DIRS for p in parts[:-1]):
        return True
    if any(fnmatch.fnmatch(parts[-1], pat) for pat in NOISE_FILES):
        return True
    norm = "/".join(parts)
    return any(norm.startswith(pre) or ("/" + pre) in "/" + norm for pre in NOISE_PREFIXES)


def counts(path):
    return not is_record(path) and not is_noise(path)


def _scope(folder, nested):
    """Pathspec: this folder minus the project folders nested inside it (the deepest folder owns a file)."""
    spec = ["."]
    for other in nested:
        rel = os.path.relpath(other, folder)
        if rel != "." and not rel.startswith(".."):
            spec.append(":(exclude)" + rel)
    return spec


def _toplevel(folder):
    out = _git(folder, "rev-parse", "--show-toplevel")
    return out.strip() if out else None


# ---- signal 1: commits ----

def commit_signal(folder, nested=()):
    """Newest commit with at least one counting path whose change survives whitespace-only filtering.
    The log is read as a stream and stopped at the first qualifying commit."""
    if not _toplevel(folder):
        return None
    cmd = ["git", "-c", "core.quotepath=off", "-C", folder, "log", "--relative", "--format=%x01%H %ct",
           "--name-only", "--"] + _scope(folder, nested)
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    except OSError:
        return None
    try:
        buf = ""
        while True:
            chunk = proc.stdout.read(65536)
            buf += chunk
            entries = buf.split("\x01")
            buf = entries.pop() if chunk else ""
            if not chunk:
                entries = [e for e in entries + [buf] if e]
                buf = ""
            for entry in entries:
                found = _qualify(folder, entry)
                if found:
                    return Signal("commit", found)
            if not chunk:
                return None
    finally:
        proc.kill()
        proc.stdout.close()
        proc.wait()


def _qualify(folder, entry):
    head, _, rest = entry.partition("\n")
    sha, _, ts = head.strip().partition(" ")
    paths = [p for p in rest.split("\n") if p and counts(p)]
    if not sha or not ts.isdigit() or not paths:
        return None
    # diff-tree --root diffs a root commit against the empty tree and any other against its parent
    diff = _git(folder, "diff-tree", "--root", "-p", "--no-commit-id", "-w", "--ignore-blank-lines",
                "--relative", sha, "--", *paths)
    return int(ts) if diff and diff.strip() else None


# ---- signal 2: uncommitted work ----

def uncommitted_signal(folder, nested=()):
    top = _toplevel(folder)
    if not top:
        return None
    out = _git(folder, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--", *_scope(folder, nested))
    if not out:
        return None
    has_head = _git(folder, "rev-parse", "--verify", "-q", "HEAD") is not None
    entries, newest = out.split("\x00"), None
    i = 0
    while i < len(entries):
        entry = entries[i]
        i += 1
        if len(entry) < 4:
            continue
        xy, path = entry[:2], entry[3:]
        if "R" in xy or "C" in xy:
            i += 1  # the next entry is the old name
        rel = os.path.relpath(os.path.join(top, path), folder)
        if not counts(rel):
            continue
        full = os.path.join(top, path)
        if "D" in xy:
            stamp = _nearest_mtime(os.path.dirname(full))
        else:
            try:
                stamp = os.path.getmtime(full)
            except OSError:
                continue
            if has_head and "M" in xy:
                diff = _git(folder, "diff", "-w", "--ignore-blank-lines", "HEAD", "--", full)
                if diff is not None and not diff.strip():
                    continue  # whitespace-only edit
        if stamp and (newest is None or stamp > newest):
            newest = stamp
    return Signal("uncommitted", newest) if newest else None


def _nearest_mtime(path):
    while path and not os.path.exists(path):
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent
    return os.path.getmtime(path) if path else None


# ---- signal 3: decisions ----

def blame_times(path):
    """{line number: epoch} for a file, or None when git cannot blame it. Uncommitted lines get the file mtime."""
    out = _git(os.path.dirname(path), "blame", "--porcelain", "--", os.path.basename(path))
    if out is None:
        return None
    times, commit_time, current, mtime = {}, {}, None, None
    for raw in out.split("\n"):
        m = re.match(r"^([0-9a-f]{40}) \d+ (\d+)", raw)
        if m:
            current = (m.group(1), int(m.group(2)))
        elif raw.startswith("committer-time ") and current:
            commit_time[current[0]] = int(raw.split()[1])
        elif raw.startswith("\t") and current:
            sha, lineno = current
            if set(sha) == {"0"}:
                if mtime is None:
                    mtime = os.path.getmtime(path)
                times[lineno] = mtime
            else:
                times[lineno] = commit_time.get(sha)
    return times


def _line_date(text):
    m = re.search(r"(\d{4}-\d{2}-\d{2})", text[:40])
    return time.mktime(time.strptime(m.group(1), "%Y-%m-%d")) if m else None


def lines_signal(kind, locations, stamp_of=None, blame_cache=None):
    """Newest time among (file, line) locations. `stamp_of(text)` may give an explicit time for a line."""
    cache = blame_cache if blame_cache is not None else {}
    newest = None
    for path, lineno in locations:
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read().split("\n")[lineno - 1]
        except (OSError, IndexError):
            continue
        stamp = stamp_of(text) if stamp_of else None
        if stamp is None:
            if path not in cache:
                cache[path] = blame_times(path)
            blame = cache[path]
            stamp = blame.get(lineno) if blame else None
            if stamp is None:
                # shortcut: blame failed; the line's own date at 00:00 local, else the file mtime
                stamp = _line_date(text) or _safe_mtime(path)
        if stamp and (newest is None or stamp > newest):
            newest = stamp
    return Signal(kind, newest) if newest else None


def _safe_mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


# ---- signal 4: pipeline items ----

TOUCHED = re.compile(r"(?:^|·)\s*touched:\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2})")


def touched_stamp(text):
    m = TOUCHED.search(text)
    return time.mktime(time.strptime(m.group(1), "%Y-%m-%d %H:%M")) if m else None


def pipeline_signal(items, blame_cache=None):
    """items: (file, item line) pairs. An item is its line plus the indented detail lines under it.
    A `touched: YYYY-MM-DD HH:MM` field on the item line is its time; line history is the fallback."""
    newest = None
    for path, lineno in items:
        try:
            with open(path, encoding="utf-8") as fh:
                lines = fh.read().split("\n")
        except OSError:
            continue
        stamp = touched_stamp(lines[lineno - 1]) if lineno - 1 < len(lines) else None
        if stamp is None:
            span = [(path, lineno)]
            n = lineno
            while n < len(lines) and lines[n].startswith((" ", "\t")):
                n += 1
                span.append((path, n))
            sig = lines_signal("pipeline", span, blame_cache=blame_cache)
            stamp = sig.time if sig else None
        if stamp and (newest is None or stamp > newest):
            newest = stamp
    return Signal("pipeline", newest) if newest else None


# ---- all four ----

def last_touch(folder, nested, decisions, pipeline, blame_cache=None):
    """The newest signal of the four, or None when the project has none."""
    found = []
    if folder:
        found.append(commit_signal(folder, nested))
        found.append(uncommitted_signal(folder, nested))
    if decisions:
        found.append(lines_signal("decision", decisions, blame_cache=blame_cache))
    if pipeline:
        found.append(pipeline_signal(pipeline, blame_cache=blame_cache))
    found = [s for s in found if s]
    return max(found, key=lambda s: s.time) if found else None


def format_time(epoch):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(epoch))
