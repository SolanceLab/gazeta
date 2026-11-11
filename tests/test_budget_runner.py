# Gazeta — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
import os
import sys
import tempfile
import time
import unittest

from fixtures import ENGINE, Tmp
from core import budget, runner
from core.contract import Ctx

FINE = '''
ID = "fine"
PRIORITY = 7
def section(ctx):
    return {"id": "fine", "priority": 7, "lines": ["fine line"], "projects": []}
'''
BOOM = '''
ID = "boom"
def section(ctx):
    raise RuntimeError("kaput")
'''
SLOW = '''
import time
ID = "slow"
TIMEOUT = 0.3
def section(ctx):
    time.sleep(3)
    return {"id": "slow", "priority": 5, "lines": ["never"]}
'''


def sec(id_, n, width=20, **kw):
    lines = ["%s line %d %s" % (id_, i, "x" * width) for i in range(n)]
    return dict({"id": id_, "priority": 10, "lines": lines, "min_lines": lines[:1], "projects": []}, **kw)


class BudgetTests(unittest.TestCase):
    def test_under_cap_is_untouched(self):
        out = budget.assemble("H", [sec("a", 3)], "F", 45, 6000)
        self.assertEqual(out.count("\n"), 5)
        self.assertNotIn("trimmed", out)

    def test_oversized_stays_under_cap_every_item_present_pointer_printed(self):
        items = [{"full": ["P%d one %s" % (i, "y" * 150), "P%d two %s" % (i, "z" * 150)],
                  "min": ["P%d one %s" % (i, "y" * 150)]} for i in range(5)]
        proj = {"id": "projects", "priority": 40, "projects": [], "items": items, "tail": [],
                "lines": [l for i in items for l in i["full"]], "min_lines": [i["min"][0] for i in items],
                "reserve": 1500, "pointer": "slice --project <id>"}
        big = sec("big", 60, 80, priority=30, reserve=4000, pointer="run it again")
        out = budget.assemble("H", [proj, big], "F", 45, 6000)
        lines = out.rstrip("\n").split("\n")
        self.assertLessEqual(len(lines), 45)
        self.assertLessEqual(len(out.rstrip("\n")), 6000)
        for i in range(5):
            self.assertIn("P%d one" % i, out)
        self.assertIn("trimmed: ", out)
        self.assertIn("run it again", out)
        for line in lines:  # nothing cut mid-line: every line is a whole original line
            self.assertTrue(line.endswith(("x" * 80, "y" * 150, "z" * 150, "F", "H", "again")) or line.startswith("trimmed"), line)

    def test_lowest_ranked_slice_shrinks_first(self):
        items = [{"full": ["P%d a" % i, "P%d b %s" % (i, "q" * 200)], "min": ["P%d a" % i]} for i in range(3)]
        proj = {"id": "p", "priority": 10, "projects": [], "items": items, "tail": [],
                "lines": [l for i in items for l in i["full"]], "min_lines": ["P0 a", "P1 a", "P2 a"]}
        out = budget.assemble("H", [proj], "F", 45, 500)
        self.assertIn("P0 b", out)
        self.assertNotIn("P2 b", out)

    def test_cannot_fit_is_visible(self):
        floor = sec("floor", 1, 400)
        out = budget.assemble("H", [floor], "F", 45, 100)
        self.assertIn("still over the cap", out)


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Tmp()
        self.specs = []
        for name, code in (("slow", SLOW), ("boom", BOOM), ("fine", FINE)):
            path = os.path.join(self.tmp.path, name + ".py")
            with open(path, "w") as fh:
                fh.write(code)
            self.specs.append(path)

    def tearDown(self):
        self.tmp.close()

    def test_throwing_and_sleeping_adapters_give_two_unavailable_lines(self):
        start = time.monotonic()
        secs = runner.run_adapters(self.specs, Ctx())
        self.assertLess(time.monotonic() - start, 2.0)
        text = budget.assemble("H", secs, "F")
        self.assertIn("slow: source unavailable (timed out", text)
        self.assertIn("boom: source unavailable (RuntimeError: kaput)", text)
        self.assertIn("fine line", text)
        self.assertEqual(text.count("source unavailable"), 2)

    def test_cli_exit_zero_within_timeout(self):
        import json
        import subprocess
        cfg = os.path.join(self.tmp.path, "engine.json")
        with open(cfg, "w") as fh:
            json.dump({"adapters": self.specs}, fh)
        engine = ENGINE
        start = time.monotonic()
        done = subprocess.run([sys.executable, os.path.join(engine, "gazeta.py"), "--config", cfg],
                              capture_output=True, text=True, timeout=10)
        self.assertEqual(done.returncode, 0)
        self.assertLess(time.monotonic() - start, 2.5)
        self.assertEqual(done.stdout.count("source unavailable"), 2)

    def test_missing_adapter_is_one_line(self):
        secs = runner.run_adapters(["public.nope"], Ctx())
        self.assertIn("source unavailable", secs[0]["lines"][0])


if __name__ == "__main__":
    unittest.main()
