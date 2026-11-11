# Gazeta — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
"""Check a written edition against simple line rules and append one verdict line to a log."""
import json
import os
import time

DEFAULT_LOG = "~/.config/gazeta/wake-checks.md"


def check_edition(text, rules):
    """Problems found in the edition text; [] means clean."""
    rules = rules or {}
    lines = text.split("\n")
    problems = []
    for prefix in rules.get("expect") or []:
        if not any(l.startswith(prefix) for l in lines):
            problems.append("missing: %s" % prefix)
    for prefix in rules.get("forbid") or []:
        if any(l.startswith(prefix) for l in lines):
            problems.append("forbidden: %s" % prefix)
    for line in lines:
        if ": source unavailable (" in line:
            problems.append("unavailable: %s" % line.split(":", 1)[0].strip())
        elif line.startswith("trimmed:"):
            problems.append("trimmed: %s" % line[len("trimmed:"):].strip()[:60])
    return problems


def _payload(stdin_text):
    try:
        data = json.loads(stdin_text) if stdin_text else {}
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _append(path, line):
    path = os.path.expanduser(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def log_check(rules, edition, stdin_text, session, now):
    """Check the edition and append one line to the log. Never raises."""
    log = DEFAULT_LOG
    stamp = ""
    try:
        log = rules.get("log", DEFAULT_LOG)
        stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(now() if callable(now) else now))
        data = _payload(stdin_text)
        sess = str(data.get("session_id") or session or "")[:8]
        source = str(data.get("source") or "?")
        problems = check_edition(edition, rules)
        verdict = "NOT CLEAN: " + "; ".join(problems) if problems else "CLEAN"
        _append(log, "- auto · %s · session %s · %s · %s" % (stamp, sess, source, verdict))
    except Exception as exc:  # noqa: BLE001
        try:
            _append(log, "- auto · %s · check failed: %s" % (stamp, type(exc).__name__))
        except Exception:  # noqa: BLE001
            pass
