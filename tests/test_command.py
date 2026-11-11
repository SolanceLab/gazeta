# Gazeta — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
"""The generic command adapter, and several command sections in one edition."""
import io
import json
import os
import sys
import time
import unittest

from fixtures import Tmp
import gazeta
from adapters.public import command
from core import runner
from core.contract import Ctx, SourceUnavailable


def script(tmp, name, body):
    path = os.path.join(tmp.path, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("import sys\nsys.stdout.reconfigure(encoding='utf-8')\n" + body)
    return path


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Tmp()
        self.addCleanup(self.tmp.close)

    def run_section(self, body, **opts):
        path = script(self.tmp, "c.py", body)
        opts.setdefault("command", [sys.executable, path])
        return command.section(Ctx(workspace=self.tmp.path, options=opts))

    def test_stdout_is_carried_unchanged(self):
        out = self.run_section("print('one')\nprint('  two')\n")
        self.assertEqual(out["lines"], ["one", "  two"])
        path = script(self.tmp, "c2.py", "print('one')\n")
        spec = "public.command:x"
        out = runner.run_adapters([spec], Ctx(workspace=self.tmp.path),
                                  options={spec: {"command": [sys.executable, path], "id": "mine", "priority": 7}})[0]
        self.assertEqual((out["id"], out["priority"]), ("mine", 7))

    def test_stdin_payload_reaches_the_command(self):
        path = script(self.tmp, "echo.py", "print(sys.stdin.read())\n")
        out = command.section(Ctx(workspace=self.tmp.path, stdin_text="payload", options={"command": [sys.executable, path]}))
        self.assertEqual(out["lines"], ["payload"])

    def test_nonzero_exit_is_unavailable_even_with_output(self):
        with self.assertRaises(SourceUnavailable) as caught:
            self.run_section("print('partial')\nsys.exit(3)\n")
        self.assertIn("exit 3", str(caught.exception))

    def test_empty_output_unavailable_unless_empty_ok(self):
        with self.assertRaises(SourceUnavailable):
            self.run_section("pass\n")
        self.assertEqual(self.run_section("pass\n", empty_ok=True)["lines"], [])

    def test_missing_command_and_unknown_program_are_unavailable(self):
        with self.assertRaises(SourceUnavailable):
            command.section(Ctx(workspace=self.tmp.path, options={}))
        with self.assertRaises(SourceUnavailable):
            command.section(Ctx(workspace=self.tmp.path, options={"command": ["/no/such/program"]}))

    def test_drop_prefixes(self):
        out = self.run_section("print('keep')\nprint('# note')\nprint('keep too')\n", drop_prefixes=["# "])
        self.assertEqual(out["lines"], ["keep", "keep too"])

    def test_drop_blocks_drops_only_the_block(self):
        body = "print('A')\nprint('REPEAT')\nprint('* one')\nprint('-> next')\nprint('  indented')\nprint('B')\n"
        out = self.run_section(body, drop_blocks=[{"start": "REPEAT", "continue": ["*", "->"]}])
        self.assertEqual(out["lines"], ["A", "B"])
        out = self.run_section("print('A')\nprint('B')\n", drop_blocks=[{"start": "REPEAT", "continue": ["*"]}])
        self.assertEqual(out["lines"], ["A", "B"])

    def test_pointer_shows_only_the_program_name(self):
        out = self.run_section("print('x')\n", command=["/bin/sh", "-c", "echo x --token=SECRET123"])
        self.assertEqual(out["pointer"], "sh")
        self.assertNotIn("SECRET123", out["pointer"])

    def test_min_prefixes_set_the_trimmed_form(self):
        out = self.run_section("print('# head')\nprint('- a')\nprint('- b')\n", min_prefixes=["# "])
        self.assertEqual(out["min_lines"], ["# head"])


class TwoSectionsTests(unittest.TestCase):
    def test_two_command_sections_at_once_keep_their_own_options(self):
        tmp = Tmp()
        self.addCleanup(tmp.close)
        a = script(tmp, "a.py", "print('from a')\n")
        b = script(tmp, "b.py", "print('from b')\nprint('# drop')\n")
        specs = ["public.command:wip", "public.command:awake"]
        options = {specs[0]: {"command": [sys.executable, a], "priority": 20},
                   specs[1]: {"command": [sys.executable, b], "id": "morning", "drop_prefixes": ["# "], "priority": 10}}
        secs = runner.run_adapters(specs, Ctx(workspace=tmp.path), options=options)
        self.assertEqual([s["id"] for s in secs], ["wip", "morning"])
        self.assertEqual(secs[0]["lines"], ["from a"])
        self.assertEqual(secs[1]["lines"], ["from b"])
        self.assertEqual([s["priority"] for s in secs], [20, 10])

    def test_unavailable_instance_is_named_by_its_instance(self):
        secs = runner.run_adapters(["public.command:todo"], Ctx())
        self.assertIn("todo: source unavailable", secs[0]["lines"][0])

    def test_option_timeout_cuts_a_slow_command(self):
        tmp = Tmp()
        self.addCleanup(tmp.close)
        slow = script(tmp, "slow.py", "import time\ntime.sleep(5)\nprint('late')\n")
        spec = "public.command:slow"
        secs = runner.run_adapters([spec], Ctx(workspace=tmp.path),
                                   options={spec: {"command": [sys.executable, slow], "timeout": 1}})
        self.assertIn("slow: source unavailable", secs[0]["lines"][0])

    def test_config_id_and_priority_win_over_what_the_adapter_returns(self):
        tmp = Tmp()
        self.addCleanup(tmp.close)
        mod = script(tmp, "own.py", "def section(ctx):\n    return {'id': 'adapter-id', 'priority': 1, 'lines': ['x']}\n")
        secs = runner.run_adapters([mod], Ctx(workspace=tmp.path), options={mod: {"id": "config-id", "priority": 9}})
        self.assertEqual((secs[0]["id"], secs[0]["priority"]), ("config-id", 9))
        secs = runner.run_adapters([mod], Ctx(workspace=tmp.path))
        self.assertEqual((secs[0]["id"], secs[0]["priority"]), ("adapter-id", 1))

    def test_configured_timeout_reaches_the_subprocess(self):
        tmp = Tmp()
        self.addCleanup(tmp.close)
        marker = os.path.join(tmp.path, "late")
        slow = script(tmp, "slow.py", "import time\ntime.sleep(2.5)\nopen(%r, 'w').close()\n" % marker)
        spec = "public.command:slow"
        secs = runner.run_adapters([spec], Ctx(workspace=tmp.path), timeouts={spec: 1.2},
                                   options={spec: {"command": [sys.executable, slow]}})
        self.assertIn("source unavailable", secs[0]["lines"][0])
        time.sleep(2.5)
        self.assertFalse(os.path.exists(marker), "the command was left running past its timeout")
        with self.assertRaises(SourceUnavailable):  # ctx.timeout wins over the option
            command.section(Ctx(workspace=tmp.path, timeout=1, options={"command": [sys.executable, slow], "timeout": 60}))

    def test_deadline_stops_waiting_and_marks_the_rest_unavailable(self):
        tmp = Tmp()
        self.addCleanup(tmp.close)
        slow = script(tmp, "slow.py", "import time\ntime.sleep(30)\nprint('late')\n")
        fast = script(tmp, "fast.py", "print('quick')\n")
        specs = ["public.command:slow", "public.command:fast"]
        options = {specs[0]: {"command": [sys.executable, slow], "timeout": 60}, specs[1]: {"command": [sys.executable, fast]}}
        start = time.monotonic()
        secs = runner.run_adapters(specs, Ctx(workspace=tmp.path), options=options, deadline=1.5)
        self.assertLess(time.monotonic() - start, 5)
        self.assertIn("slow: source unavailable", secs[0]["lines"][0])
        self.assertEqual(secs[1]["lines"], ["quick"])

    def test_edition_shows_both_sections_from_a_config(self):
        tmp = Tmp()
        self.addCleanup(tmp.close)
        a = script(tmp, "a.py", "print('alpha line')\n")
        b = script(tmp, "b.py", "print('beta line')\n")
        specs = ["public.command:first", "public.command:second"]
        cfg = os.path.join(tmp.path, "config.json")
        with open(cfg, "w") as fh:
            json.dump({"workspace": tmp.path, "adapters": specs,
                       "options": {specs[0]: {"command": [sys.executable, a]}, specs[1]: {"command": [sys.executable, b]}}}, fh)
        buf = io.StringIO()
        self.assertEqual(gazeta.main(["--config", cfg], stdout=buf), 0)
        self.assertIn("alpha line", buf.getvalue())
        self.assertIn("beta line", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
