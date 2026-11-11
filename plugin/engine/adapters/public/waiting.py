# Gazeta — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
"""One line per project outside the top five that has an item waiting on you or being built.

Options: {"statuses": [..]} names the work-map statuses to list, first one first (default waiting, building).
"""
import re
from core import ranking

PRIORITY = 20
MORE = "work_map.py slice --house --status waiting"
ID = "waiting"
MAX_LINES = 5
WAITING_ON = re.compile(r"waiting-on-[a-z0-9][a-z0-9-]*")
STATUSES = ("waiting", "building")


def _matches(wanted, status):
    """"waiting" also covers work-map's waiting-on-<name>; any other status matches itself."""
    return status == wanted or (wanted == "waiting" and bool(WAITING_ON.fullmatch(status or "")))
RESERVE = 400


def section(ctx):
    result = ranking.compute(ctx)
    shown = {pid for pid, _ in result["top"]}
    seen, rows = set(), []
    for status in ctx.options.get("statuses") or STATUSES:  # the first status listed comes first
        for r in ctx.work_map.records():
            if r["kind"] in ("pipeline", "task") and _matches(status, r["status"]) and r["project"] not in shown | seen:
                seen.add(r["project"])
                rows.append("%s: %s (%s)" % (r["project"], r["id"].split("/")[-1].split(":")[-1], r["status"]))
    if not rows:
        return {"id": ID, "priority": PRIORITY, "lines": ["waiting: nothing waiting or building outside the top five"],
                "projects": []}
    kept, extra = rows[:MAX_LINES], len(rows) - MAX_LINES
    lines = kept + (["+%d more → %s" % (extra, MORE)] if extra > 0 else [])
    return {"id": ID, "priority": PRIORITY, "lines": lines, "min_lines": ["+%d more → %s" % (len(rows), MORE)],
            "projects": [], "reserve": RESERVE, "pointer": MORE}
