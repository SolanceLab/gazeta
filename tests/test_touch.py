# Gazeta — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
import os
import unittest

from fixtures import DAY, NOW, Tmp, commit, make_repo, write, git
from core import touch, ranking


class TouchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Tmp()
        self.repo = make_repo(self.tmp.path)
        self.old = NOW - 100 * DAY
        write(self.repo, "p/code.py", "print(1)\n")
        write(self.repo, "p/DECISIONS.md", "- 2026-01-01 · a\n")
        commit(self.repo, "init", self.old)
        self.folder = os.path.join(self.repo, "p")

    def tearDown(self):
        self.tmp.close()

    def test_commit_signal_uses_committer_time(self):
        self.assertEqual(touch.commit_signal(self.folder), touch.Signal("commit", self.old))

    def test_uncommitted_beats_older_commit_unstaged_and_staged(self):
        write(self.repo, "p/code.py", "print(2)\n", mtime=NOW - 5 * DAY)
        self.assertEqual(touch.uncommitted_signal(self.folder).time, NOW - 5 * DAY)
        git(self.repo, "add", "p/code.py")  # staged now
        self.assertEqual(touch.uncommitted_signal(self.folder).time, NOW - 5 * DAY)
        best = touch.last_touch(self.folder, [], [], [])
        self.assertEqual((best.kind, best.time), ("uncommitted", NOW - 5 * DAY))

    def test_deletion_counts_by_parent_folder_time(self):
        os.remove(os.path.join(self.repo, "p/code.py"))
        os.utime(self.folder, (NOW - 2 * DAY, NOW - 2 * DAY))
        self.assertEqual(touch.uncommitted_signal(self.folder).time, NOW - 2 * DAY)

    def test_whitespace_only_edit_does_not_count(self):
        write(self.repo, "p/code.py", "print(1)   \n\n", mtime=NOW - DAY)
        self.assertIsNone(touch.uncommitted_signal(self.folder))

    def test_records_only_commit_does_not_move_it(self):
        write(self.repo, "p/DECISIONS.md", "- 2026-01-01 · a\n- 2026-02-02 · b\n")
        write(self.repo, "p/PIPELINE.md", "x\n")
        commit(self.repo, "records", NOW - DAY)
        self.assertEqual(touch.commit_signal(self.folder).time, self.old)

    def test_reformat_only_commit_does_not_move_it(self):
        write(self.repo, "p/code.py", "print(1)  \n\n")
        commit(self.repo, "reformat", NOW - DAY)
        self.assertEqual(touch.commit_signal(self.folder).time, self.old)

    def test_plans_commit_counts(self):
        write(self.repo, "p/plans/2026-11-10-x.md", "plan\n")
        commit(self.repo, "plan", NOW - DAY)
        self.assertEqual(touch.commit_signal(self.folder).time, NOW - DAY)

    def test_ignore_list_noise_does_not_rank(self):
        write(self.repo, "p/__pycache__/m.cpython-39.pyc", "x", mtime=NOW)
        write(self.repo, "p/run.log", "x", mtime=NOW)
        write(self.repo, "p/node_modules/a/b.js", "x", mtime=NOW)
        self.assertIsNone(touch.uncommitted_signal(self.folder))
        write(self.repo, "p/__pycache__/n.pyc", "x")
        commit(self.repo, "noise", NOW - DAY)
        self.assertEqual(touch.commit_signal(self.folder).time, self.old)

    def test_nested_folder_touches_the_deepest_project(self):
        write(self.repo, "p/inner/new.py", "x = 1\n", mtime=NOW - DAY)
        inner = os.path.join(self.folder, "inner")
        self.assertEqual(touch.uncommitted_signal(inner).time, NOW - DAY)
        self.assertIsNone(touch.uncommitted_signal(self.folder, nested=[inner]))
        commit(self.repo, "inner", NOW - DAY)
        self.assertEqual(touch.commit_signal(inner).time, NOW - DAY)
        self.assertEqual(touch.commit_signal(self.folder, nested=[inner]).time, self.old)

    def test_not_a_repo_gives_no_git_signal(self):
        bare = os.path.join(self.tmp.path, "plain")
        os.makedirs(bare)
        self.assertIsNone(touch.commit_signal(bare))
        self.assertIsNone(touch.uncommitted_signal(bare))


class LineSignalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Tmp()
        self.repo = make_repo(self.tmp.path)
        self.dec = write(self.repo, "DECISIONS.md", "- 2026-01-01 · applies: [a] · one\n- 2026-01-02 · applies: [b] · two\n")
        commit(self.repo, "d", NOW - 30 * DAY)

    def tearDown(self):
        self.tmp.close()

    def test_decision_uses_commit_time_of_its_line(self):
        with open(self.dec, "a") as fh:
            fh.write("- 2026-02-02 · applies: [a] · three\n")
        commit(self.repo, "d2", NOW - 10 * DAY)
        self.assertEqual(touch.lines_signal("decision", [(self.dec, 1)]).time, NOW - 30 * DAY)
        self.assertEqual(touch.lines_signal("decision", [(self.dec, 3)]).time, NOW - 10 * DAY)

    def test_uncommitted_decision_line_uses_file_mtime(self):
        with open(self.dec, "a") as fh:
            fh.write("- 2026-03-03 · applies: [a] · new\n")
        os.utime(self.dec, (NOW - 3 * DAY, NOW - 3 * DAY))
        self.assertEqual(touch.lines_signal("decision", [(self.dec, 3)]).time, NOW - 3 * DAY)

    def test_blame_failure_falls_back_to_line_date(self):
        loose = os.path.join(self.tmp.path, "loose.md")
        with open(loose, "w") as fh:
            fh.write("- 2026-05-06 · applies: [a]\n")
        sig = touch.lines_signal("decision", [(loose, 1)])
        self.assertEqual(touch.format_time(sig.time), "2026-05-06 00:00")


class PipelineSignalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Tmp()
        self.repo = make_repo(self.tmp.path)
        self.pl = write(self.repo, "p/PIPELINE.md",
                        "# p\n\n- **Item one** · id: one · status: planned\n  - detail\n- **Item two** · id: two · status: planned\n")
        commit(self.repo, "p", NOW - 50 * DAY)

    def tearDown(self):
        self.tmp.close()

    def test_item_line_change_ranks_via_blame(self):
        write(self.repo, "p/PIPELINE.md",
              "# p\n\n- **Item one** · id: one · status: building\n  - detail\n- **Item two** · id: two · status: planned\n")
        commit(self.repo, "upd", NOW - 4 * DAY)
        self.assertEqual(touch.pipeline_signal([(self.pl, 3)]).time, NOW - 4 * DAY)
        self.assertEqual(touch.pipeline_signal([(self.pl, 5)]).time, NOW - 50 * DAY)

    def test_detail_line_change_counts_for_its_item(self):
        write(self.repo, "p/PIPELINE.md",
              "# p\n\n- **Item one** · id: one · status: planned\n  - detail changed\n- **Item two** · id: two · status: planned\n")
        commit(self.repo, "detail", NOW - 2 * DAY)
        self.assertEqual(touch.pipeline_signal([(self.pl, 3)]).time, NOW - 2 * DAY)

    def test_touched_stamp_beats_blame(self):
        write(self.repo, "p/PIPELINE.md",
              "# p\n\n- **Item one** · id: one · status: planned · touched: 2026-11-10 20:15\n  - detail\n- **Item two** · id: two\n")
        commit(self.repo, "stamp", NOW - 1 * DAY)
        sig = touch.pipeline_signal([(self.pl, 3)])
        self.assertEqual(touch.format_time(sig.time), "2026-11-10 20:15")

    def test_touched_stamp_parser(self):
        self.assertIsNone(touch.touched_stamp("- **x** · id: x · why: untouched: 2026-01-01 10:00 nope"))
        self.assertIsNotNone(touch.touched_stamp("- **x** · id: x · touched: 2026-01-01 10:00"))


class RankTests(unittest.TestCase):
    def test_no_window_five_of_six_even_when_old(self):
        sigs = {"p%d" % i: touch.Signal("commit", NOW - 400 * DAY - i * DAY) for i in range(6)}
        top, count = ranking.rank(sigs)
        self.assertEqual([p for p, _ in top], ["p0", "p1", "p2", "p3", "p4"])
        self.assertEqual(count, 6)

    def test_fewer_than_five_and_untouched_left_out(self):
        sigs = {"a": touch.Signal("commit", 5), "b": touch.Signal("commit", 9), "c": touch.Signal("commit", 7), "d": None}
        top, count = ranking.rank(sigs)
        self.assertEqual([p for p, _ in top], ["b", "c", "a"])
        self.assertEqual(count, 3)

    def test_ties_break_by_id(self):
        sigs = {"b": touch.Signal("commit", 5), "a": touch.Signal("commit", 5)}
        self.assertEqual([p for p, _ in ranking.rank(sigs)[0]], ["a", "b"])


if __name__ == "__main__":
    unittest.main()
