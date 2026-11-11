# Gazeta — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
"""Call the work-map CLI (never imported): the project inventory, records and slices."""
import json
import os
import subprocess
import sys
import threading

from .contract import SourceUnavailable


class WorkMap:
    def __init__(self, script, config, python=None, timeout=5.0):
        self.script, self.config = script, config
        self.python = python or sys.executable or "python3"
        self.timeout = timeout
        self.base = os.path.dirname(os.path.abspath(config))  # work-map resolves source paths against this
        self._lock = threading.Lock()
        self._records = None

    def run(self, *args):
        cmd = [self.python, self.script, "--config", self.config] + list(args) + ["--json"]
        try:
            done = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SourceUnavailable("work-map: %s" % type(exc).__name__)
        if done.returncode != 0:
            raise SourceUnavailable("work-map exit %d: %s" % (done.returncode, done.stderr.strip()[:80]))
        try:
            return json.loads(done.stdout)
        except ValueError:
            raise SourceUnavailable("work-map printed no JSON")

    def records(self):
        """Every record, once per run (query with no words matches all)."""
        with self._lock:
            if self._records is None:
                self._records = self.run("query", "")
            return self._records

    def slice(self, project, status="open", limit=12):
        return self.run("slice", "--project", project, "--status", status,
                        "--limit", str(limit), "--house-limit", "0")

    def abspath(self, source_file):
        return source_file if os.path.isabs(source_file) else os.path.join(self.base, source_file)

    def config_data(self):
        try:
            with open(self.config, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return {}  # shortcut: JSON configs only; a TOML config just loses folder discovery
