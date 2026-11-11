# Gazeta — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
"""Rank projects by last touch and pick the slice set. No time window: the newest five, however old."""
from concurrent.futures import ThreadPoolExecutor

from . import touch
from .contract import SourceUnavailable
from .inventory import load_inventory

TOP_N = 5


def rank(touches, n=TOP_N):
    """touches: {project id: Signal or None}. Newest first, ties by id; untouched projects are left out."""
    touched = [(pid, sig) for pid, sig in touches.items() if sig]
    touched.sort(key=lambda item: (-item[1].time, item[0]))
    return touched[:n], len(touched)


def compute(ctx):
    """Inventory + touches + ranking, computed once per run and shared by every adapter that needs it."""
    with ctx.lock:
        cached = ctx.shared.get("ranking")
        if cached is None:
            try:
                cached = _compute(ctx)
            except Exception as exc:
                cached = exc
            ctx.shared["ranking"] = cached
    if isinstance(cached, Exception):
        raise cached
    return cached


def _compute(ctx):
    if ctx.work_map is None:
        raise SourceUnavailable("work-map not configured")
    projects = load_inventory(ctx.work_map)
    folders = [p["folder"] for p in projects.values() if p["folder"]]
    blame_cache = {}

    def one(project):
        folder = project["folder"]
        nested = [f for f in folders if folder and f != folder and f.startswith(folder.rstrip("/") + "/")]
        return project["id"], touch.last_touch(folder, nested, project["decisions"], project["pipeline"], blame_cache)

    # blame results are cached per file; fill them first so the threads below only read
    for path in {p for proj in projects.values() for p, _ in proj["decisions"] + proj["pipeline"]}:
        blame_cache[path] = touch.blame_times(path)
    with ThreadPoolExecutor(max_workers=8) as pool:
        touches = dict(pool.map(one, projects.values()))
    top, touched_count = rank(touches)
    return {"projects": projects, "touches": touches, "top": top, "touched": touched_count}
