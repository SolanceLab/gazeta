# Gazeta — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
import io
import json
import os
import shutil
import subprocess
import sys
import unittest

from fixtures import DAY, ENGINE, NOW, Tmp, commit, fake_work_map, make_repo, rec, write
import gazeta
from adapters.public import named, projects, waiting
from core.contract import Ctx
from core.workmap import WorkMap


class World:
    """A temp workspace: one git repo, N project folders, a fake work-map over them."""
    def __init__(self, ages_days, extra_records=()):
        self.tmp = Tmp()
        self.repo = make_repo(self.tmp.path, "ws")
        records, pipeline_files, map_lines = [], [], []
        for i, age in enumerate(ages_days):
            pid = "proj%d" % i
            write(self.repo, "%s/code.py" % pid, "x = %d\n" % i)
            write(self.repo, "%s/PIPELINE.md" % pid, "# %s\n" % pid)
            commit(self.repo, "c" + pid, NOW - age * DAY, pid)
            pipeline_files.append(os.path.join(self.repo, pid, "PIPELINE.md"))
            records.append(rec("project", "project:" + pid, pid, "building", source=("PIPELINE.md", i + 1)))
            map_lines.append("- **P%d** · id: %s · status: building · aka: %s · why: x" % (i, pid, "old%d" % i if i == 5 else "none"))
        records.extend(extra_records)
        self.script, self.config = fake_work_map(self.tmp.path, records, pipeline_files, "\n".join(map_lines) + "\n")

    def ctx(self, prompt=""):
        return Ctx(workspace=self.repo, clock=lambda: NOW, session_id="s1", prompt=prompt,
                   work_map=WorkMap(self.script, self.config))

    def close(self):
        self.tmp.close()


class ProjectsTests(unittest.TestCase):
    def test_no_window_five_full_slices_from_old_projects(self):
        w = World([400 + i for i in range(6)])
        self.addCleanup(w.close)
        out = projects.section(w.ctx())
        self.assertEqual(out["projects"], ["proj0", "proj1", "proj2", "proj3", "proj4"])
        self.assertEqual(len(out["items"]), 5)
        self.assertTrue(all(len(i["full"]) == 2 and len(i["min"]) == 1 for i in out["items"]))
        self.assertNotIn("only", " ".join(out["tail"]))

    def test_three_eligible_gives_three_slices_and_only_three_touched(self):
        w = World([1, 2, 3])
        self.addCleanup(w.close)
        out = projects.section(w.ctx())
        self.assertEqual(len(out["projects"]), 3)
        self.assertEqual(out["tail"], ["only 3 touched"])

    def test_slice_line_names_signal_and_pointer(self):
        w = World([1], [rec("ship", "ship:r@1", "proj0", date="2026-11-01", gist="shipped 1.0 abc")])
        self.addCleanup(w.close)
        line1, line2 = projects.section(w.ctx())["items"][0]["full"]
        self.assertTrue(line1.startswith("proj0 · building · touched commit "))
        self.assertIn("last: shipped 1.0 abc", line1)
        self.assertIn("work_map.py slice --project proj0", line2)

    def test_work_map_missing_is_unavailable_not_a_crash(self):
        from core import runner
        secs = runner.run_adapters(["public.projects"], Ctx(workspace="."))
        self.assertIn("source unavailable (SourceUnavailable: work-map not configured)", secs[0]["lines"][0])


class WaitingTests(unittest.TestCase):
    def test_lists_projects_outside_top_five_only(self):
        extra = [rec("pipeline", "pipeline:other/job", "other", "waiting", source=("PIPELINE.md", 9)),
                 rec("pipeline", "pipeline:proj0/job", "proj0", "waiting", source=("PIPELINE.md", 9)),
                 rec("pipeline", "pipeline:third/build", "third", "building", source=("PIPELINE.md", 9))]
        w = World([1, 2], extra)
        self.addCleanup(w.close)
        out = waiting.section(w.ctx())
        self.assertEqual(out["lines"], ["other: job (waiting)", "third: build (building)"])

    def test_long_list_collapses_to_pointer(self):
        extra = [rec("pipeline", "pipeline:x%d/j" % i, "x%d" % i, "waiting", source=("PIPELINE.md", 9)) for i in range(8)]
        w = World([1], extra)
        self.addCleanup(w.close)
        out = waiting.section(w.ctx())
        self.assertEqual(len(out["lines"]), 6)
        self.assertTrue(out["lines"][-1].startswith("+3 more"))


class NamedTests(unittest.TestCase):
    NAMES = {"alpha": [], "beta": ["old-beta"], "gamma": [], "hos-app": []}

    def test_pick_named_rules(self):
        pick = named.pick_named
        self.assertEqual(pick("look at Beta please", self.NAMES, {"alpha"}), ["beta"])      # not in top 5 -> slice
        self.assertEqual(pick("look at alpha", self.NAMES, {"alpha"}), [])                  # in top 5 -> nothing
        self.assertEqual(pick("gamma then old-beta", self.NAMES, set()), ["gamma", "beta"])  # two names, order named
        self.assertEqual(pick("nothing relevant, betamax", self.NAMES, set()), [])          # unmatched, whole word
        self.assertEqual(pick("the hos-app.", self.NAMES, set()), ["hos-app"])
        self.assertEqual(pick("a b c", {"a": [], "b": [], "c": []}, set()), ["a", "b"])     # at most two extra

    def test_fit_keeps_whole_slices_under_budget(self):
        s = [{"full": ["a" * 200, "b" * 200], "min": ["a" * 200]}, {"full": ["c" * 200, "d" * 200], "min": ["c" * 200]}]
        out = named.fit(s, 700)
        self.assertEqual(len(out), 3)  # first full, second only min

    def test_first_prompt_marker_once_per_session(self):
        t = Tmp()
        self.addCleanup(t.close)
        self.assertTrue(named.first_prompt(t.path, "sess-1"))
        self.assertFalse(named.first_prompt(t.path, "sess-1"))
        self.assertTrue(named.first_prompt(t.path, "sess-2"))
        self.assertTrue(named.first_prompt(t.path, "../weird id"))  # never escapes the seen dir
        self.assertEqual(len(os.listdir(t.path)), 3)

    def test_cli_named_flow_adds_slice_once(self):
        w = World([1, 2, 3, 4, 5, 6, 7])  # proj5 and proj6 sit outside the top five; proj5 has aka old5
        self.addCleanup(w.close)
        cfg = os.path.join(w.tmp.path, "engine.json")
        with open(cfg, "w") as fh:
            json.dump({"work_map": {"script": w.script, "config": w.config}}, fh)
        seen = os.path.join(w.tmp.path, "seen")

        def run(text, session):
            buf = io.StringIO()
            gazeta.main(["--config", cfg, "--named", text, "--session", session, "--seen-dir", seen], stdout=buf)
            return buf.getvalue()

        out = run("please look at old5", "s1")
        self.assertTrue(out.startswith("proj5 "), out)
        self.assertEqual(run("please look at proj5", "s1"), "")      # second prompt, same session
        self.assertEqual(run("nothing here", "s2"), "")              # unmatched
        self.assertEqual(run("proj0 only", "s3"), "")                # top five already
        both = run("proj6 then proj5", "s4")                         # two names add two, in the order named
        self.assertLess(both.index("proj6 \u00b7"), both.index("proj5 \u00b7"))
        self.assertEqual(len(both.strip().split("\n")), 4)

    def test_cli_named_failure_prints_one_line(self):
        t = Tmp()
        self.addCleanup(t.close)
        buf = io.StringIO()
        rc = gazeta.main(["--named", "anything", "--session", "z", "--seen-dir", t.path], stdout=buf)
        self.assertEqual(rc, 0)
        self.assertEqual(buf.getvalue().strip(), "named slice unavailable")


class ShadowAndPackagingTests(unittest.TestCase):
    def test_shadow_writes_edition_to_out(self):
        w = World([1, 2])
        self.addCleanup(w.close)
        cfg = os.path.join(w.tmp.path, "engine.json")
        with open(cfg, "w") as fh:
            json.dump({"work_map": {"script": w.script, "config": w.config}}, fh)
        out = os.path.join(w.tmp.path, "sub", "shadow.md")
        self.assertEqual(gazeta.main(["--config", cfg, "--shadow", "--out", out], clock=lambda: NOW), 0)
        text = open(out).read()
        self.assertTrue(text.startswith("Gazeta · "))
        self.assertIn("proj0 · building", text)

    def test_packaging_public_copy_runs_alone_without_house_words(self):
        t = Tmp()
        self.addCleanup(t.close)
        dest = os.path.join(t.path, "pkg")
        os.makedirs(os.path.join(dest, "adapters"))
        shutil.copytree(os.path.join(ENGINE, "core"), os.path.join(dest, "core"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(os.path.join(ENGINE, "adapters", "public"), os.path.join(dest, "adapters", "public"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy(os.path.join(ENGINE, "adapters", "__init__.py"), os.path.join(dest, "adapters"))
        shutil.copy(os.path.join(ENGINE, "gazeta.py"), dest)
        env = dict(os.environ, HOME=os.path.join(t.path, "emptyhome"))
        done = subprocess.run([sys.executable, os.path.join(dest, "gazeta.py")], capture_output=True, text=True,
                              cwd=t.path, env=env, timeout=20)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(done.stdout.startswith("Gazeta \u00b7 "), done.stdout)
        self.assertIn("source unavailable", done.stdout)  # public sections only, honestly unavailable
        # the package imports nothing from outside itself and the standard library
        probe = ("import json, os, sys, sysconfig\n"
                 "sys.path.insert(0, %r)\n"
                 "import gazeta\n"
                 "gazeta.main([], stdout=open(os.devnull, 'w'))\n"
                 "std = {os.path.realpath(sysconfig.get_paths()[k]) for k in ('stdlib', 'platstdlib')}\n"
                 "out = []\n"
                 "for m in list(sys.modules.values()):\n"
                 "    f = getattr(m, '__file__', None)\n"
                 "    if f and not any(os.path.realpath(f).startswith(s) for s in std) and not os.path.realpath(f).startswith(%r):\n"
                 "        out.append(f)\n"
                 "print(json.dumps(out))\n") % (dest, os.path.realpath(dest))
        # -S: skip site startup hooks (sitecustomize, distro helpers) that some Pythons load before any code runs
        probed = subprocess.run([sys.executable, "-I", "-S", "-c", probe], capture_output=True, text=True, cwd=t.path, env=env, timeout=20)
        self.assertEqual(probed.returncode, 0, probed.stderr)
        self.assertEqual(json.loads(probed.stdout.splitlines()[-1]), [])
        self.assertEqual(os.listdir(env["HOME"]) if os.path.isdir(env["HOME"]) else [], [])  # nothing written to HOME

if __name__ == "__main__":
    unittest.main()
