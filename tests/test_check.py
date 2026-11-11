# Gazeta — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
import io
import json
import os
import sys
import unittest
from unittest import mock

from fixtures import Tmp
import gazeta
from core import check

NOW = 1762857600


class CheckEditionTests(unittest.TestCase):
    def test_clean(self):
        self.assertEqual(check.check_edition("Gazeta · x\nproj0 · a\n", {"expect": ["Gazeta", "proj0"], "forbid": ["bad"]}), [])

    def test_missing_and_forbidden(self):
        p = check.check_edition("Gazeta\nbad line\n", {"expect": ["proj0"], "forbid": ["bad"]})
        self.assertEqual(p, ["missing: proj0", "forbidden: bad"])

    def test_unavailable_and_trimmed(self):
        p = check.check_edition("waiting: source unavailable (timeout)\ntrimmed: " + "z" * 90 + "\n", {})
        self.assertEqual(p[0], "unavailable: waiting")
        self.assertEqual(p[1], "trimmed: " + "z" * 60)


class MainCheckTests(unittest.TestCase):
    def _cfg(self, t, log):
        cfg = os.path.join(t.path, "engine.json")
        with open(cfg, "w") as fh:
            json.dump({"workspace": t.path, "adapters": [], "check": {"expect": ["Gazeta"], "forbid": ["nope"], "log": log}}, fh)
        return cfg

    def test_shadow_logs_one_line(self):
        t = Tmp()
        self.addCleanup(t.close)
        log = os.path.join(t.path, "sub", "wake.md")
        out = os.path.join(t.path, "ed.md")
        payload = json.dumps({"session_id": "abcdef123456", "source": "compact"})
        with mock.patch.object(sys, "stdin", io.StringIO(payload)):
            rc = gazeta.main(["--config", self._cfg(t, log), "--shadow", "--stdin", "--out", out], clock=lambda: NOW)
        self.assertEqual(rc, 0)
        lines = open(log).read().splitlines()
        self.assertEqual(len(lines), 1)
        for word in ("abcdef12", "compact", "CLEAN"):
            self.assertIn(word, lines[0])
        self.assertNotIn("abcdef123", lines[0])
        print("SAMPLE:", lines[0])

    def test_unwritable_log_still_exits_zero(self):
        t = Tmp()
        self.addCleanup(t.close)
        out = os.path.join(t.path, "ed.md")
        rc = gazeta.main(["--config", self._cfg(t, t.path), "--shadow", "--out", out], clock=lambda: NOW)
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.getsize(out) > 0)

    def test_failing_clock_in_check_is_logged_not_raised(self):
        t = Tmp()
        self.addCleanup(t.close)
        log = os.path.join(t.path, "log.md")

        def bad_clock():
            raise RuntimeError("clock")
        check.log_check({"log": log}, "x\n", "", "s1", bad_clock)
        with open(log, encoding="utf-8") as fh:
            self.assertIn("check failed: RuntimeError", fh.read())


if __name__ == "__main__":
    unittest.main()
