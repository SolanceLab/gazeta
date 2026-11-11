# Gazeta — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
"""Any command's output as one section: run it, carry its stdout into the edition.

Name one instance per command with "public.command:<name>" in the config's "adapters" list, and key that
whole spec in "options". Options:
  command      list of words to run (required; "~" is expanded in each word)
  id, priority, timeout   applied by the runner: the section's name (default: the part after the colon),
               its trim order (lower is kept longer, default 50) and the seconds before it is shown as unavailable
               (default 10); the command is killed at that time
  drop_prefixes  lines starting with any of these are dropped
  drop_blocks  [{"start": prefix, "continue": [prefix, ..]}]: a line starting with "start" is dropped together
               with the lines after it that start with one of "continue" or are indented
  empty_ok     true: no output is a clean empty section; false (default): no output is unavailable
  min_prefixes lines starting with any of these are all that is kept when the edition must be trimmed
  reserve      characters the section may use before it is shrunk first
A command that exits non-zero is unavailable, whatever it printed.
"""
import os
import subprocess

from core.contract import SourceUnavailable

TIMEOUT = 10
PRIORITY = 50


def _drop_blocks(lines, blocks):
    starts = [(b["start"], tuple(b.get("continue") or ())) for b in blocks if b.get("start")]
    kept, skipping = [], None
    for line in lines:
        hit = next((cont for start, cont in starts if line.startswith(start)), None)
        if hit is not None:
            skipping = hit
            continue
        if skipping is not None and ((skipping and line.startswith(skipping)) or line[:1].isspace()):
            continue
        skipping = None
        kept.append(line)
    return kept


def section(ctx):
    opts = ctx.options
    command = [os.path.expanduser(str(part)) for part in opts.get("command") or []]
    if not command:
        raise SourceUnavailable("no command configured")
    timeout = float(ctx.timeout if ctx.timeout is not None else opts.get("timeout", TIMEOUT))
    try:
        done = subprocess.run(command, input=ctx.stdin_text or "", capture_output=True, text=True,
                              timeout=max(0.1, timeout - 0.5), cwd=ctx.workspace if os.path.isdir(ctx.workspace) else None)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SourceUnavailable(type(exc).__name__)
    if done.returncode != 0:  # partial output from a failed run is not a clean bill
        raise SourceUnavailable("exit %d" % done.returncode)
    out = done.stdout.rstrip("\n")
    if not out.strip():
        if opts.get("empty_ok"):
            lines = []
        else:
            raise SourceUnavailable("no output")
    else:
        lines = out.split("\n")
        while lines and not lines[0].strip():
            lines.pop(0)
        prefixes = tuple(opts.get("drop_prefixes") or ())
        if prefixes:
            lines = [l for l in lines if not l.startswith(prefixes)]
        lines = _drop_blocks(lines, opts.get("drop_blocks") or [])
    sec = {"priority": int(opts.get("priority", PRIORITY)), "lines": lines,
           "projects": [], "pointer": os.path.basename(command[0])}
    if opts.get("min_prefixes"):
        sec["min_lines"] = [l for l in lines if l.startswith(tuple(opts["min_prefixes"]))]
    if opts.get("reserve") is not None:
        sec["reserve"] = opts["reserve"]
    return sec
