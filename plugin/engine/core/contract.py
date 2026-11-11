# Gazeta — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
"""The adapter contract: what an adapter receives and what it returns.

An adapter is a Python module with `section(ctx) -> dict`:
    {"id": str, "priority": int, "lines": [str], "min_lines": [str], "projects": [ids]}
Optional keys: "items" (list of {"full": [..], "min": [..]}, rank order, for one-by-one
shrinking), "tail" (lines kept after the items), "reserve" (characters the section may use
before it is shrunk first), "pointer" (command shown on a "trimmed:" line).
Optional module attributes: ID, PRIORITY, TIMEOUT (seconds).
A spec may name one instance of a module as "module:name" (eg. public.command:wip); the options keyed by
that whole spec may carry "id", "priority" and "timeout"; they win over the module's attributes and over
what the adapter returns. ctx.timeout is the effective timeout in seconds (the adapter should finish inside it).
"""
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional


class SourceUnavailable(Exception):
    """Raise from an adapter when its source cannot be read; the reason is shown in the edition."""


@dataclass
class Ctx:
    workspace: str = "."
    clock: Callable[[], float] = None  # epoch seconds; tests inject a fixed one
    session_id: str = ""
    prompt: str = ""
    stdin_text: str = ""
    timeout: Optional[float] = None  # effective seconds this adapter may take; set by the runner
    options: Dict[str, Any] = field(default_factory=dict)  # this adapter's own options
    work_map: Optional[Any] = None
    shared: Dict[str, Any] = field(default_factory=dict)  # memo shared by all adapters of one run
    lock: Any = field(default_factory=threading.RLock)

    def now(self):
        import time
        return self.clock() if self.clock else time.time()


def normalize(raw, fallback_id, fallback_priority):
    """Return a validated section dict, or raise ValueError."""
    if not isinstance(raw, dict):
        raise ValueError("adapter returned %s, not a section" % type(raw).__name__)
    lines = _lines(raw.get("lines"))
    sec = {
        "id": str(raw.get("id") or fallback_id),
        "priority": int(raw.get("priority", fallback_priority)),
        "lines": lines,
        "min_lines": _lines(raw["min_lines"]) if raw.get("min_lines") is not None else list(lines),
        "projects": list(raw.get("projects") or []),
    }
    if raw.get("items") is not None:
        sec["items"] = [{"full": _lines(i.get("full")), "min": _lines(i.get("min", i.get("full")))}
                        for i in raw["items"]]
        sec["tail"] = _lines(raw.get("tail"))
    for key in ("reserve", "pointer"):
        if raw.get(key) is not None:
            sec[key] = raw[key]
    return sec


def _lines(value):
    out = []
    for item in value or []:
        out.extend(str(item).split("\n"))
    return out


def unavailable(section_id, reason, priority=50):
    line = "%s: source unavailable (%s)" % (section_id, reason)
    return {"id": section_id, "priority": priority, "lines": [line], "min_lines": [line],
            "projects": [], "unavailable": True}
