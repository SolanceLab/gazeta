# Changelog

## 0.1.1

- The README names and links [work-map](https://github.com/SolanceLab/work-map), the companion plugin the `projects` and `waiting` sections read, with install lines for both and how to point Gazeta at it.
- `waiting` also counts work-map's `waiting-on-<name>` statuses.

## 0.1.0

First public release.

- Wake-up edition built by rule: the five most recently touched projects as two-line slices, one line each for the other projects with something waiting or being built, and a size cap that trims in a fixed order and always says what it trimmed.
- Sections come from adapters named in a config file; one failing or slow adapter becomes one "source unavailable" line and never blanks the edition.
- `public.command`: any command's output as a section, with `drop_prefixes`, `drop_blocks`, `min_prefixes`, `empty_ok`, `timeout`, `priority`; several instances at once with `public.command:<name>`.
- Claude Code plugin with a SessionStart hook and a skill; Codex plugin with the skill only (Codex has no plugin hooks).
