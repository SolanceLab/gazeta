# Gazeta — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
"""The session-start hook, run as the plugin runs it."""
import json
import os
import subprocess
import sys
import time
import unittest

from fixtures import ENGINE, Tmp

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(REPO, "plugin")


def hook_command():
    with open(os.path.join(PLUGIN, "hooks", "hooks.json"), encoding="utf-8") as fh:
        data = json.load(fh)
    entries = data["hooks"]["SessionStart"]
    assert len(entries) == 1 and "matcher" not in entries[0]
    return entries[0]["hooks"][0]["command"]


def run_hook(root, config, cwd, home):
    """Run the hook command as Claude Code does: the plugin root and the plugin setting arrive as environment variables."""
    env = dict(os.environ, HOME=home, CLAUDE_PLUGIN_ROOT=root)
    env.pop("CLAUDE_PLUGIN_OPTION_CONFIG_PATH", None)
    if config is not None:
        env["CLAUDE_PLUGIN_OPTION_CONFIG_PATH"] = config
    return subprocess.run(["sh", "-c", hook_command()], input='{"session_id": "s1"}', capture_output=True, text=True,
                          cwd=cwd, env=env, timeout=30)


class HookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Tmp()
        self.addCleanup(self.tmp.close)

    def test_hook_with_temp_config_prints_the_header_and_a_command_section(self):
        cfg = os.path.join(self.tmp.path, "config.json")
        with open(cfg, "w") as fh:
            json.dump({"workspace": self.tmp.path, "adapters": ["public.command:hello"],
                       "options": {"public.command:hello": {"command": ["echo", "hello edition"]}}}, fh)
        done = run_hook(PLUGIN, cfg, self.tmp.path, self.tmp.path)
        self.assertEqual(done.returncode, 0, done.stderr)
        lines = done.stdout.splitlines()
        self.assertTrue(lines[0].startswith("Gazeta · "), done.stdout)
        self.assertIn("hello edition", lines)

    def test_hook_with_no_config_file_still_prints_an_edition(self):
        done = run_hook(PLUGIN, os.path.join(self.tmp.path, "missing.json"), self.tmp.path, self.tmp.path)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(done.stdout.startswith("Gazeta · "), done.stdout)
        self.assertIn("source unavailable", done.stdout)

    def test_hook_never_puts_the_setting_into_the_shell_text(self):
        self.assertNotIn("user_config", hook_command())
        marker = os.path.join(self.tmp.path, "pwned")
        evil = "$(touch %s)`touch %s`\";touch %s;\"" % (marker, marker, marker)
        done = run_hook(PLUGIN, evil, self.tmp.path, self.tmp.path)
        self.assertEqual(done.returncode, 0)
        self.assertFalse(os.path.exists(marker))
        self.assertTrue(done.stdout.startswith("Gazeta \u00b7 "), done.stdout)

    def test_hook_default_config_is_the_home_config(self):
        cfgdir = os.path.join(self.tmp.path, ".config", "gazeta")
        os.makedirs(cfgdir)
        with open(os.path.join(cfgdir, "config.json"), "w") as fh:
            json.dump({"workspace": self.tmp.path, "adapters": ["public.command:homed"],
                       "options": {"public.command:homed": {"command": ["echo", "from home config"]}}}, fh)
        done = run_hook(PLUGIN, None, self.tmp.path, self.tmp.path)
        self.assertIn("from home config", done.stdout.splitlines())

    def test_hook_prints_inside_its_timeout_when_an_adapter_hangs(self):
        with open(os.path.join(PLUGIN, "hooks", "hooks.json"), encoding="utf-8") as fh:
            hook_timeout = json.load(fh)["hooks"]["SessionStart"][0]["hooks"][0]["timeout"]
        slow = os.path.join(self.tmp.path, "slow.py")
        with open(slow, "w") as fh:
            fh.write("import time\ntime.sleep(60)\n")
        spec = "public.command:slow"
        cfg = os.path.join(self.tmp.path, "config.json")
        with open(cfg, "w") as fh:  # the adapter's own timeout is far longer than the deadline
            json.dump({"workspace": self.tmp.path, "adapters": [spec], "deadline": 1.5,
                       "timeouts": {spec: 50}, "options": {spec: {"command": [sys.executable, slow]}}}, fh)
        start = time.monotonic()
        done = run_hook(PLUGIN, cfg, self.tmp.path, self.tmp.path)
        self.assertLess(time.monotonic() - start, 10)
        self.assertLess(1.5, hook_timeout)
        self.assertEqual(done.returncode, 0)
        self.assertTrue(done.stdout.startswith("Gazeta \u00b7 "), done.stdout)
        self.assertIn("slow: source unavailable", done.stdout)

    def test_default_deadline_is_below_the_hook_timeout(self):
        sys.path.insert(0, ENGINE)
        from core import runner
        with open(os.path.join(PLUGIN, "hooks", "hooks.json"), encoding="utf-8") as fh:
            hook_timeout = json.load(fh)["hooks"]["SessionStart"][0]["hooks"][0]["timeout"]
        self.assertLess(runner.DEFAULT_DEADLINE, hook_timeout)

    def test_hook_that_cannot_run_says_so_in_one_line_and_exits_zero(self):
        done = run_hook(os.path.join(self.tmp.path, "nowhere"), "x.json", self.tmp.path, self.tmp.path)
        self.assertEqual(done.returncode, 0)
        self.assertEqual(done.stdout.strip(), "Gazeta did not run.")


class ManifestTests(unittest.TestCase):
    def test_both_manifests_and_changelog_name_the_same_version(self):
        versions = set()
        for rel in (".claude-plugin", ".codex-plugin"):
            with open(os.path.join(PLUGIN, rel, "plugin.json"), encoding="utf-8") as fh:
                versions.add(json.load(fh)["version"])
        with open(os.path.join(REPO, "CHANGELOG.md"), encoding="utf-8") as fh:
            top = next(l for l in fh if l.startswith("## "))
        self.assertEqual(versions, {top[3:].strip()})


if __name__ == "__main__":
    unittest.main()
