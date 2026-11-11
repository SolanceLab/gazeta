#!/usr/bin/env python3
# Gazeta — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
"""Gazeta engine entry. Writes the wake-up edition by rule; adapters come from the config file.

  gazeta.py --shadow [--out PATH] [--config engine.json]
  gazeta.py --named TEXT --session ID --seen-dir DIR [--config engine.json]

Config (JSON): workspace, work_map {script, config}, adapters [..], timeouts {adapter: seconds},
options {adapter: {..}}, cap {lines, chars}, deadline (seconds, default 20).
Without --config the file named by $CLAUDE_PLUGIN_OPTION_CONFIG_PATH (the plugin setting) is used. With no config only the public adapters run.
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from core import budget, check, runner  # noqa: E402
from core.contract import Ctx  # noqa: E402
from core.workmap import WorkMap  # noqa: E402

DEFAULT_ADAPTERS = ["public.projects", "public.waiting"]
CONFIG_ENV = "CLAUDE_PLUGIN_OPTION_CONFIG_PATH"
NAMED_TIMEOUT = 1.5
DEFAULT_OUT = os.path.join("~", ".config", "gazeta", "shadow-edition.md")
NAMED = "public.named"


def load_config(path):
    if not path:
        path = os.environ.get(CONFIG_ENV)  # the plugin setting, passed by Claude Code as an environment variable
    if not path:
        return {}
    with open(os.path.expanduser(path), encoding="utf-8") as fh:
        return json.load(fh)


def make_ctx(cfg, session_id="", prompt="", stdin_text="", clock=None):
    wm_cfg = cfg.get("work_map") or {}
    wm = WorkMap(os.path.expanduser(wm_cfg["script"]), os.path.expanduser(wm_cfg["config"])) \
        if wm_cfg.get("script") and wm_cfg.get("config") else None
    return Ctx(workspace=os.path.expanduser(cfg.get("workspace", os.getcwd())), clock=clock,
               session_id=session_id, prompt=prompt, stdin_text=stdin_text, work_map=wm)


def build_edition(cfg, ctx):
    sections = runner.run_adapters(cfg.get("adapters", DEFAULT_ADAPTERS), ctx,
                                   timeouts=cfg.get("timeouts"), options=cfg.get("options"),
                                   deadline=float(cfg.get("deadline", runner.DEFAULT_DEADLINE)))
    cap = cfg.get("cap", {})
    header = "Gazeta · %s" % time.strftime("%Y-%m-%d %H:%M", time.localtime(ctx.now()))
    footer = "More: work_map.py slice --project <id> · full edition: gazeta.py --shadow"
    return budget.assemble(header, sections, footer, cap.get("lines", budget.DEFAULT_CAP_LINES),
                           cap.get("chars", budget.DEFAULT_CAP_CHARS))


def named_text(cfg, ctx):
    """The first-message slice text ('' when nothing to add). Never raises."""
    out = runner.run_adapters([NAMED], ctx, timeouts={NAMED: NAMED_TIMEOUT})[0]
    if out.get("unavailable"):
        return "named slice unavailable"
    return "\n".join(out["lines"])


def main(argv=None, stdout=None, clock=None):
    stdout = stdout or sys.stdout
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--shadow", action="store_true", help="write the edition to --out instead of printing it")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--stdin", action="store_true", help="read the hook payload on stdin and pass it to adapters")
    ap.add_argument("--named", metavar="TEXT")
    ap.add_argument("--session", default="")
    ap.add_argument("--seen-dir")
    args = ap.parse_args(argv)
    try:
        cfg = load_config(args.config)
    except (OSError, ValueError) as exc:
        print("gazeta: config unreadable (%s); running with defaults" % exc, file=sys.stderr)
        cfg = {}
    if args.named is not None:
        from adapters.public import named
        if args.seen_dir and not named.first_prompt(args.seen_dir, args.session):
            return 0
        text = named_text(cfg, make_ctx(cfg, args.session, args.named, clock=clock))
        if text:
            stdout.write(text + "\n")
        return 0
    stdin_text = sys.stdin.read() if args.stdin else ""
    ctx = make_ctx(cfg, args.session, stdin_text=stdin_text, clock=clock)
    edition = build_edition(cfg, ctx)
    if args.shadow:
        out = os.path.expanduser(args.out)
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(edition)
        if isinstance(cfg.get("check"), dict):
            check.log_check(cfg["check"], edition, stdin_text, args.session, ctx.now)
    else:
        stdout.write(edition)
    return 0


if __name__ == "__main__":
    sys.exit(main())
