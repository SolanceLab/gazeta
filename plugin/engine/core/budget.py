# Gazeta — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
"""Fit the edition into the size cap. Overflow is deterministic and always visible.

Order of shrinking, only while over the cap:
  1. sections over their own reserve: items drop to their min form, lowest-ranked first,
     then the whole section drops to min_lines plus a "trimmed:" pointer;
  2. every other section, last-rendered first, the same two steps.
A selected item is never dropped: its min form is the floor.
"""

DEFAULT_CAP_LINES = 45
DEFAULT_CAP_CHARS = 6000


class _Part:
    def __init__(self, section):
        self.section = section
        items = section.get("items")
        self.state = ["full"] * len(items) if items is not None else None
        self.whole_min = False

    def lines(self):
        s = self.section
        if self.whole_min:
            dropped = len(s["lines"]) - len(s["min_lines"])
            return list(s["min_lines"]) + ["trimmed: %d lines → %s" % (dropped, s.get("pointer", "see the source"))]
        if self.state is None:
            return list(s["lines"])
        out = []
        for item, mode in zip(s["items"], self.state):
            out.extend(item[mode])
        return out + list(s.get("tail", []))

    def chars(self):
        return len("\n".join(self.lines()))

    def can_shrink_item(self):
        return self.state is not None and "full" in self.state and not self.whole_min

    def shrink_item(self):
        # last in rank order = lowest ranked
        for idx in range(len(self.state) - 1, -1, -1):
            if self.state[idx] == "full" and self.section["items"][idx]["full"] != self.section["items"][idx]["min"]:
                self.state[idx] = "min"
                return True
            if self.state[idx] == "full":
                self.state[idx] = "min"
        return False

    def can_shrink_whole(self):
        s = self.section
        if self.whole_min or self.state is not None:
            return False  # items sections already reach their floor through the items
        return len(s["min_lines"]) < len(s["lines"])


def assemble(header, sections, footer, cap_lines=DEFAULT_CAP_LINES, cap_chars=DEFAULT_CAP_CHARS):
    parts = [_Part(s) for s in sorted(sections, key=lambda s: s["priority"])]

    def render():
        out = [header]
        for p in parts:
            out.extend(p.lines())
        out.append(footer)
        return out

    def over(lines):
        return len(lines) > cap_lines or len("\n".join(lines)) > cap_chars

    def over_reserve(p):
        reserve = p.section.get("reserve")
        return reserve is not None and p.chars() > reserve

    while over(render()):
        ordered = list(reversed(parts))
        pools = [[p for p in ordered if over_reserve(p)], [p for p in ordered if not over_reserve(p)]]
        if not _shrink_one(pools):
            break
    lines = render()
    if over(lines):
        lines.insert(len(lines) - 1, "trimmed: edition still over the cap (%d lines, %d chars)"
                     % (len(lines), len("\n".join(lines))))
    return "\n".join(lines) + "\n"


def _shrink_one(pools):
    for pool in pools:
        for p in pool:
            if p.can_shrink_item() and p.shrink_item():
                return True
        for p in pool:
            if p.can_shrink_whole():
                p.whole_min = True
                return True
    return False
