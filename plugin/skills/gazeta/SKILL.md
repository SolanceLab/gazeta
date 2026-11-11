---
name: gazeta
description: Read the Gazeta wake-up edition printed at session start, and add a new source to it with an adapter.
---

# Gazeta

Gazeta prints a short edition when a session starts. Read it first: it is the shortest way to know what was touched last and what is waiting.

## Reading the edition

- The first line is `Gazeta · <date time>`; the last line points to the full edition.
- Each source (a section) is a few lines under its own name. `projects` lists the five most recently touched projects as two lines each; `waiting` lists one line per other project with something waiting or being built; any command section carries that command's output.
- `<name>: source unavailable (<reason>)` means that source could not be read this time (not configured, command failed, timed out). Say so; do not guess what it would have shown.
- `trimmed: N lines → <pointer>` means the edition hit its size cap and cut a section; run the pointer to see the rest.
- To see the whole edition without the cap's cut, run `python3 <plugin>/engine/gazeta.py --shadow --out /tmp/gazeta.md` and read the file.
- With no config file only `projects` and `waiting` run, and both say "source unavailable" until a work-map is configured. That is normal, not a fault.

## Adding a source

1. Easiest: a command section. In the config file (`~/.config/gazeta/config.json` unless the plugin setting says otherwise) add the spec to `adapters` and key the same spec in `options`:

```
{"adapters": ["public.projects", "public.waiting", "public.command:todo"],
 "options": {"public.command:todo": {"command": ["cat", "~/todo.txt"], "priority": 30}}}
```

   Options: `command`, `id`, `priority`, `timeout`, `drop_prefixes`, `drop_blocks`, `min_prefixes`, `empty_ok`, `reserve`. Use one `public.command:<name>` spec per command.
2. Own adapter: a Python file with `section(ctx)` returning `{"id", "priority", "lines", "projects"}`; list its path in `adapters`. Raise `SourceUnavailable` from `core.contract` when the source cannot be read. The full contract is in CONTRACT.md.
3. Run `python3 <plugin>/engine/gazeta.py --config <config file>` and read the result before relying on it.

Limits: the edition is capped (default 45 lines, 6000 characters; set `cap` in the config); each source has a timeout, and one failing source never blanks the edition.
