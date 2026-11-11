# Gazeta — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
"""The slice schema: two lines per project, pointers not details. Line 1 alone is the min form."""
from . import touch

LAST_CHARS = 80
ITEM_KINDS = ("pipeline", "task")


def _clip(text, n):
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[:n - 3] + "..."


def build_slice(ctx, project, signal):
    """Return {"full": [line1, line2], "min": [line1]} for one project."""
    wm = ctx.work_map
    pid = project["id"]
    ships = [r for r in wm.records() if r["kind"] == "ship" and r["project"] == pid]
    ships.sort(key=lambda r: r.get("date", ""), reverse=True)
    last = _clip(ships[0]["gist"], LAST_CHARS) if ships else "no ship recorded"
    line1 = "%s · %s · touched %s %s · last: %s" % (
        pid, project["status"], signal.kind, touch.format_time(signal.time), last)
    try:
        rows = wm.slice(pid)
        items = ["%s (%s)" % (r["id"].split("/")[-1].split(":")[-1], r["status"])
                 for r in rows if r["kind"] in ITEM_KINDS][:2]
        decisions = sorted((r for r in rows if r["kind"] == "decision"), key=lambda r: r.get("date", ""), reverse=True)
        decided = decisions[0]["id"].split(":", 1)[-1] if decisions else "none"
        line2 = "open: %s · decided: %s → work_map.py slice --project %s" % (
            "; ".join(items) or "none", decided, pid)
    except Exception as exc:
        line2 = "open: unavailable (%s) → work_map.py slice --project %s" % (_clip(exc, 60), pid)
    return {"full": [line1, line2], "min": [line1]}
