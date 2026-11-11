# Gazeta — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
"""Run adapters in parallel threads, each with its own timeout; one failure never blanks the edition."""
import importlib
import importlib.util
import os
import threading

from .contract import normalize, unavailable
from dataclasses import replace

DEFAULT_TIMEOUT = 2.0
DEFAULT_PRIORITY = 50
DEFAULT_DEADLINE = 20.0


def load_adapter(spec):
    """spec is a dotted name under adapters/ (eg. public.projects), optionally ":instance" after it, or a path to a .py file."""
    if spec.endswith(".py"):
        name = "gazeta_adapter_" + os.path.splitext(os.path.basename(spec))[0]
        found = importlib.util.spec_from_file_location(name, spec)
        module = importlib.util.module_from_spec(found)
        found.loader.exec_module(module)
        return module
    return importlib.import_module("adapters." + spec.split(":", 1)[0])


def _label(spec):
    if spec.endswith(".py"):
        return os.path.splitext(os.path.basename(spec))[0]
    return spec.split(":", 1)[1] if ":" in spec else spec.split(".")[-1]


def run_adapters(specs, ctx, timeouts=None, options=None, deadline=None):
    """Return one normalized section per spec, in spec order. Never raises.

    deadline: seconds after which the runner stops waiting for anyone; sections still running are unavailable."""
    import time
    begin = time.monotonic()
    timeouts, options = timeouts or {}, options or {}
    jobs = []
    for spec in specs:
        job = {"spec": spec, "label": _label(spec), "result": None, "priority": DEFAULT_PRIORITY,
               "timeout": float(timeouts.get(spec, DEFAULT_TIMEOUT))}
        try:
            module = load_adapter(spec)
            opts = options.get(spec, {})
            named = ":" in spec and not spec.endswith(".py")
            job["label"] = opts.get("id") or (job["label"] if named else getattr(module, "ID", job["label"]))
            job["priority"] = int(opts.get("priority", getattr(module, "PRIORITY", DEFAULT_PRIORITY)))
            job["timeout"] = float(timeouts.get(spec, opts.get("timeout", getattr(module, "TIMEOUT", DEFAULT_TIMEOUT))))
            if deadline is not None:
                job["timeout"] = min(job["timeout"], float(deadline))
            job["opts"] = opts
            job["thread"] = threading.Thread(
                target=_call, args=(job, module, replace(ctx, options=opts, timeout=job["timeout"])), daemon=True)
        except Exception as exc:  # a missing or broken adapter is one line, not a crash
            job["result"] = unavailable(job["label"], _reason(exc), job["priority"])
        jobs.append(job)
    for job in jobs:
        if "thread" in job:
            job["thread"].start()
    start = begin
    for job in jobs:
        thread = job.get("thread")
        if thread is None:
            continue
        thread.join(max(0.0, job["timeout"] - (time.monotonic() - start)))
        if job["result"] is None:
            job["result"] = unavailable(job["label"], "timed out after %gs" % job["timeout"], job["priority"])
            job["abandoned"] = True
    return [job["result"] for job in jobs]


def _call(job, module, ctx):
    try:
        sec = normalize(module.section(ctx), job["label"], job["priority"])
        # the config's id and priority for this spec win over whatever the adapter returned
        if ctx.options.get("id"):
            sec["id"] = str(ctx.options["id"])
        if ctx.options.get("priority") is not None:
            sec["priority"] = int(ctx.options["priority"])
        if not job.get("abandoned"):
            job["result"] = sec
    except Exception as exc:
        job["result"] = unavailable(job["label"], _reason(exc), job["priority"])


def _reason(exc):
    text = str(exc).strip().replace("\n", " ")
    return (type(exc).__name__ + (": " + text if text else ""))[:120]
