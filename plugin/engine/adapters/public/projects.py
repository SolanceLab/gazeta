# Gazeta — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
"""Top-five recently touched projects, each as a two-line slice (work-map is the source)."""
from concurrent.futures import ThreadPoolExecutor

from core import ranking, slices

TIMEOUT = 10  # shortcut: plan says 2 s for public adapters; touch over ~46 folders needs more. Tune on the first shadow run.
PRIORITY = 40
ID = "projects"
RESERVE = 1500


def section(ctx):
    result = ranking.compute(ctx)
    top = result["top"]
    with ThreadPoolExecutor(max_workers=5) as pool:
        built = list(pool.map(lambda item: slices.build_slice(ctx, result["projects"][item[0]], item[1]), top))
    tail = []
    if result["touched"] < ranking.TOP_N:
        tail.append("only %d touched" % result["touched"])
    lines = [l for b in built for l in b["full"]] + tail
    return {"id": ID, "priority": PRIORITY, "lines": lines,
            "min_lines": [l for b in built for l in b["min"]] + tail,
            "items": [{"full": b["full"], "min": b["min"]} for b in built], "tail": tail,
            "projects": [pid for pid, _ in top], "reserve": RESERVE,
            "pointer": "work_map.py slice --project <id>"}
