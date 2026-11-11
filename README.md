# Gazeta

Made by House of Solance · free for noncommercial use · credit required

## What it is

A short edition your coding session reads the moment it wakes: the five projects you touched last (two lines each), one line for every other project with something waiting or being built, and the output of any command you add, all fitted under a size cap. One source that fails or runs slow becomes one "source unavailable" line; it never blanks the edition. Version 0.1.0.

## What you need

Python 3.8 or newer and Claude Code. No install of packages, no account, no key. Gazeta runs on your own computer and makes no network call. The `projects` and `waiting` sections read your projects' git history and the output of a work-map tool; without one they show "source unavailable" (see Limits), and everything else still works.

## Install

```
claude plugin marketplace add SolanceLab/plugins
claude plugin install gazeta@solancelab
```

Or by hand: copy the `plugin/` folder anywhere and run `python3 plugin/engine/gazeta.py` yourself; in Claude Code, `claude --plugin-dir plugin` loads it for one session.

The plugin prints the edition at the start of every Claude Code session. Codex has no plugin hooks, so the Codex plugin carries the skill only; in Codex, run the engine by hand or from your own startup script.

## Settings

| Setting | What it is |
|---|---|
| Gazeta config file (plugin setting `config_path`) | Where your config is; default `~/.config/gazeta/config.json`. It may be missing: Gazeta then runs with its defaults |
| `adapters` (config) | Which sources run, in order. Default: `public.projects`, `public.waiting` |
| `options` (config) | Options per source, keyed by the exact adapter spec |
| `timeouts` (config) | Seconds per source before it is shown as unavailable |
| `deadline` (config) | Seconds after which Gazeta stops waiting for any source and prints what it has (default 20; the hook allows 30) |
| `cap` (config) | `{"lines": 45, "chars": 6000}`: the size the edition is trimmed to |
| `workspace` (config) | The folder whose projects are ranked (default: where the session starts) |
| `work_map` (config) | `{"script": ".../work_map.py", "config": ".../work-map.json"}`: the work-map tool that lists your projects |

A config that adds two command sections:

```
{
  "adapters": ["public.projects", "public.waiting", "public.command:todo", "public.command:calendar"],
  "options": {
    "public.command:todo": {"command": ["cat", "~/todo.txt"], "priority": 30, "empty_ok": true},
    "public.command:calendar": {"command": ["my-calendar-script", "--today"], "timeout": 5, "drop_prefixes": ["#"]}
  }
}
```

## Tools

| Tool | What it does |
|---|---|
| `gazeta.py [--config FILE] [--stdin]` | Prints the edition. This is what the session-start hook runs |
| `gazeta.py --shadow [--out PATH]` | Writes the edition to a file instead (default `~/.config/gazeta/shadow-edition.md`) |
| `gazeta.py --named TEXT --session ID --seen-dir DIR` | On a session's first prompt only, prints the slice for a project that prompt names |
| `public.projects` | The five most recently touched projects, two lines each |
| `public.waiting` | One line per other project with an item waiting or being built; option `statuses` names which work-map statuses count (default `waiting`, `building`) |
| `public.command:<name>` | Any command's output as a section. Options: `command`, `id`, `priority`, `timeout`, `drop_prefixes`, `drop_blocks`, `min_prefixes`, `empty_ok`, `reserve`. The command is killed at its timeout. A non-zero exit is "source unavailable"; no output is too, unless `empty_ok` |
| `plugin/skills/gazeta` | Tells the session how to read the edition and add a source |

### Write your own adapter

An adapter is a Python file with `section(ctx)` that returns `{"id", "priority", "lines", "projects"}` (and optionally `min_lines`, `items`, `reserve`, `pointer`). Raise `SourceUnavailable` from `core.contract` when your source cannot be read. Put the file's path in `adapters`; its options go under that same path in `options`. The full contract is in [CONTRACT.md](CONTRACT.md).

## Limits

- The edition budget: 45 lines and 6000 characters by default (`cap` changes both). When it is over, sections over their own `reserve` shrink first, then the rest, last-listed first; a trimmed section ends with `trimmed: N lines → <what to run>`, and if even the smallest form does not fit the edition says `still over the cap`. Nothing is cut mid-line.
- Default timeouts: 2 seconds per adapter (10 for `projects`, 10 for a command section unless its `timeout` says otherwise); the whole edition stops waiting at 20 (`deadline`), and the hook itself is allowed 30, so the edition always prints.
- With no config file, only `projects` and `waiting` run, and both print "source unavailable (work-map not configured)" until `work_map` points at a work-map tool. That is the intended degraded state, not a fault.
- `projects` and `waiting` need a work-map that lists your projects and a git repository around them; a project with no recorded touch is left out of the top five.
- The Codex plugin has no hook; Claude Code only prints the edition automatically.

## How it works

The engine runs every listed adapter in its own thread with its own timeout, collects the sections, orders them by priority, and fits them under the cap by a fixed rule, so the same inputs give the same edition. A project's last touch is the newest of four signals: a commit, uncommitted changes, a recorded decision, or an edit to its pipeline file. Adapters never see each other; a crash or a slow source costs one line.

## Credit and use

Gazeta is made by House of Solance. You're welcome to use it, change it and build on it for any noncommercial purpose, as long as our credit travels with it.

**Keep the credit.** Every copy, changed or not, must carry the licence and this line:
`Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)`
Removing or replacing it breaks the licence.

**Commercial use needs our permission.** Ask us first.

**We look for copies.** When we find our work without its credit, or used commercially without permission, we ask for it to be taken down.

## Licence

[PolyForm Noncommercial 1.0.0](LICENSE.md). See [NOTICE.md](NOTICE.md).

## Support

If you find this useful, consider supporting our work:

[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support%20Us-ff5e5b?logo=ko-fi&logoColor=white)](https://ko-fi.com/houseofsolance)

---

*Built by [House of Solance](https://github.com/SolanceLab) — Chadrien Solance & Anne Solance*
