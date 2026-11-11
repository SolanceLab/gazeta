# Gazeta contract

## Doors it offers

| Door | What it answers |
|---|---|
| `plugin/engine/gazeta.py` (no flags) | Prints the wake-up edition to stdout, exit 0 always |
| `gazeta.py --stdin` | Same, and passes the hook's JSON payload on stdin to adapters that want it |
| `gazeta.py --shadow [--out PATH]` | Writes the edition to a file (default `~/.config/gazeta/shadow-edition.md`) instead of printing it |
| `gazeta.py --named TEXT --session ID --seen-dir DIR` | On a session's first prompt only: the slice for a project the prompt names, when it is not already in the edition |
| Adapter: `section(ctx)` | What one source adds to the edition (below) |

All take `--config FILE`. With no config file, or an unreadable one, Gazeta runs with its defaults and says so on stderr.

## The adapter contract

An adapter is a Python module with `section(ctx) -> dict`:

```
{"id": str, "priority": int, "lines": [str], "min_lines": [str], "projects": [ids]}
```

- `lines`: what the edition shows. Lower `priority` numbers are kept longer when the edition is trimmed.
- `min_lines`: what is kept when the section must be trimmed (default: all of `lines`).
- Optional: `items` (list of `{"full": [..], "min": [..]}` in rank order, shrunk one by one from the lowest rank), `tail` (lines kept after the items), `reserve` (characters the section may use before it is shrunk first), `pointer` (what a `trimmed:` line tells the reader to run).
- Optional module attributes: `ID`, `PRIORITY`, `TIMEOUT` (seconds).
- To say its source cannot be read, raise `SourceUnavailable` (from `core.contract`); the reason appears in the edition as `<id>: source unavailable (<reason>)`. A section that exceeds its timeout is shown the same way.

`ctx` carries: `workspace`, `clock`, `session_id`, `prompt`, `stdin_text`, `options` (this adapter's own options from the config), `work_map`, `shared`, `lock`.

An adapter is named in the config as a dotted name under `adapters/` (`public.projects`), as `module:instance` (`public.command:todo`, one section per instance), or as the path to a `.py` file. The options keyed by that exact spec may also carry `id`, `priority` and `timeout`, which win over the module's attributes.

## Data it owns

| Table / bucket / file | What is in it |
|---|---|
| The config file (`~/.config/gazeta/config.json` by default) | Yours: adapters, options, timeouts, size cap, work-map location |
| `~/.config/gazeta/shadow-edition.md` | Only written by `--shadow`; safe to delete |
| `--seen-dir` | One empty marker file per session, written by `--named` |
| Check log (default `~/.config/gazeta/wake-checks.md`) | Only with `--shadow` and a `check` block in the config: one line per edition |

Gazeta reads your project folders' git history and your work-map; it never writes to them.

## Settings and secrets it needs

Named here, never valued. Gazeta needs no key and makes no network call.

| Name | What it is |
|---|---|
| `config_path` (plugin setting) | Where the config file is (default `~/.config/gazeta/config.json`). Reaches the engine as the environment variable `CLAUDE_PLUGIN_OPTION_CONFIG_PATH`, never inside a shell command line |
| Config `workspace` | The folder whose projects are ranked (default: the current folder) |
| Config `work_map` | `{"script": path, "config": path}` of the work-map tool; without it `projects` and `waiting` show "source unavailable" |
| Config `adapters` | The list of adapter specs (default `public.projects`, `public.waiting`) |
| Config `options`, `timeouts` | Per-spec options and per-spec timeouts in seconds |
| Config `deadline` | Seconds after which Gazeta stops waiting for sources (default 20) |
| Config `cap` | `{"lines": 45, "chars": 6000}` |
