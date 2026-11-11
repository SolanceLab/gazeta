# Gazeta — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
"""Projects as work-map reads them, with their folders and the lines that mention them."""
import glob
import os

from .contract import SourceUnavailable


def load_inventory(wm):
    """Return {id: {id, status, aka, folder, decisions: [(abs file, line)], pipeline: [(abs file, line)]}}."""
    records = wm.records()
    projects = {}
    for r in records:
        if r["kind"] == "project":
            projects[r["project"]] = {"id": r["project"], "status": r["status"], "aka": _aka(wm, r),
                                      "folder": None, "decisions": [], "pipeline": []}
    if not projects:
        raise SourceUnavailable("work-map lists no projects")
    for folder in _pipeline_folders(wm):
        pid = os.path.basename(folder)
        if pid in projects:
            projects[pid]["folder"] = folder
    for r in records:
        where = (wm.abspath(r["source"]["file"]), r["source"]["line"])
        if r["kind"] == "decision":
            for target in r.get("links", {}).get("applies-to", []):
                if target.startswith("project:") and target[8:] in projects:
                    projects[target[8:]]["decisions"].append(where)
        elif r["kind"] == "pipeline" and r["project"] in projects:
            projects[r["project"]]["pipeline"].append(where)
    return projects


def _aka(wm, record):
    """The map line carries `aka: a, b`; work-map's JSON does not repeat it, so read the line."""
    try:
        with open(wm.abspath(record["source"]["file"]), encoding="utf-8") as fh:
            line = fh.read().split("\n")[record["source"]["line"] - 1]
    except (OSError, IndexError):
        return []
    for field in line.split(" · "):
        field = field.strip()
        if field.startswith("aka:"):
            return [a.strip() for a in field[4:].split(",") if a.strip() and a.strip() != "none"]
    return []


def _pipeline_folders(wm):
    cfg = wm.config_data().get("pipeline", [])
    cfg = [cfg] if isinstance(cfg, str) else cfg
    for pattern in cfg:
        pattern = pattern if os.path.isabs(pattern) else os.path.join(wm.base, pattern)
        for path in glob.glob(pattern):
            yield os.path.dirname(os.path.abspath(path))
