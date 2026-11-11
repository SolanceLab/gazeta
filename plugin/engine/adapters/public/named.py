# Gazeta — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
"""A project named in the first message gets its slice (once per session)."""
import hashlib
import os
import re

from core import ranking, slices

TIMEOUT = 1.5
PRIORITY = 10
ID = "named"
MAX_CHARS = 700
MAX_EXTRA = 2


def pick_named(prompt, names, top_ids, limit=MAX_EXTRA):
    """Pure. names: {project id: [aka names]}. Whole-word, case-insensitive match; order of first mention;
    projects already in the top five add nothing."""
    found = []
    for pid, aka in names.items():
        positions = []
        for name in [pid] + list(aka):
            m = re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(name), prompt or "", re.I)
            if m:
                positions.append(m.start())
        if positions and pid not in top_ids:
            found.append((min(positions), pid))
    return [pid for _, pid in sorted(found)][:limit]


def fit(slice_list, max_chars=MAX_CHARS):
    """Whole slices only, in order; the first slice drops to its min form if it alone is too long."""
    lines, used = [], 0
    for item in slice_list:
        for form in ("full", "min"):
            cost = len("\n".join(item[form])) + (1 if lines else 0)
            if used + cost <= max_chars:
                lines.extend(item[form])
                used += cost
                break
    return lines


def section(ctx):
    result = ranking.compute(ctx)
    names = {pid: p["aka"] for pid, p in result["projects"].items()}
    picked = pick_named(ctx.prompt, names, {pid for pid, _ in result["top"]})
    built = []
    for pid in picked:
        sig = result["touches"].get(pid)
        if sig:
            built.append(slices.build_slice(ctx, result["projects"][pid], sig))
    lines = fit(built)
    return {"id": ID, "priority": PRIORITY, "lines": lines, "projects": picked}


def seen_marker(seen_dir, session_id):
    safe = session_id if re.fullmatch(r"[A-Za-z0-9_-]{1,80}", session_id or "") else hashlib.sha256(
        (session_id or "").encode()).hexdigest()[:32]
    return os.path.join(seen_dir, safe)


def first_prompt(seen_dir, session_id):
    """True exactly once per session: creates the marker. A resumed session keeps its marker."""
    marker = seen_marker(seen_dir, session_id)
    os.makedirs(seen_dir, exist_ok=True)
    try:
        os.close(os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644))
    except FileExistsError:
        return False
    return True
