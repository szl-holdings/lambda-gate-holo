from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "hf_static_space.py"
SPEC = importlib.util.spec_from_file_location("hf_static_space_inventory", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

REPOSITORY = MODULE.load_config()["source_repository"]
REPOSITORY_ID = MODULE.TARGET_REPOSITORY_IDS[REPOSITORY]
BEFORE = "b" * 40
SOURCE = "a" * 40
HEAD = "d" * 40


def exact_row(*, row_id: int = 70, number: int = 7) -> dict:
    return {
        "id": row_id,
        "number": number,
        "state": "closed",
        "merged_at": "2026-08-28T15:00:00Z",
        "merge_commit_sha": SOURCE,
        "base": {
            "ref": "main",
            "sha": BEFORE,
            "repo": {"full_name": REPOSITORY, "id": REPOSITORY_ID},
        },
        "head": {
            "ref": "release-candidate",
            "sha": HEAD,
            "repo": {"full_name": REPOSITORY, "id": REPOSITORY_ID},
        },
    }


class PostMergePullInventoryTests(unittest.TestCase):
    def select(self, rows: list[dict]) -> dict:
        return MODULE._select_exact_merged_pull(
            rows, REPOSITORY, REPOSITORY_ID, BEFORE, SOURCE
        )

    def test_exact_singleton_survives_unrelated_closed_rows(self) -> None:
        older = exact_row(row_id=60, number=6)
        older["merge_commit_sha"] = "c" * 40
        newer = exact_row(row_id=80, number=8)
        newer["base"]["sha"] = "e" * 40
        selected = self.select([newer, exact_row(), older])
        self.assertEqual(selected["id"], 70)

    def test_two_exact_rows_fail_ambiguously(self) -> None:
        with self.assertRaisesRegex(MODULE.ContractError, "unambiguous"):
            self.select([exact_row(), exact_row(row_id=71, number=8)])

    def test_no_exact_row_fails_closed(self) -> None:
        row = exact_row()
        row["merge_commit_sha"] = "c" * 40
        with self.assertRaisesRegex(MODULE.ContractError, "unambiguous"):
            self.select([row])

    def test_every_governed_tuple_field_is_required(self) -> None:
        mutations = {
            "state": lambda row: row.__setitem__("state", "open"),
            "merged_at": lambda row: row.__setitem__("merged_at", None),
            "merge_sha": lambda row: row.__setitem__("merge_commit_sha", "c" * 40),
            "base_ref": lambda row: row["base"].__setitem__("ref", "dev"),
            "base_sha": lambda row: row["base"].__setitem__("sha", "c" * 40),
            "base_name": lambda row: row["base"]["repo"].__setitem__(
                "full_name", "foreign/repository"
            ),
            "base_id": lambda row: row["base"]["repo"].__setitem__(
                "id", REPOSITORY_ID + 1
            ),
            "head_ref": lambda row: row["head"].__setitem__("ref", ""),
            "head_sha": lambda row: row["head"].__setitem__("sha", "bad"),
            "head_name": lambda row: row["head"]["repo"].__setitem__(
                "full_name", "foreign/repository"
            ),
            "head_id": lambda row: row["head"]["repo"].__setitem__(
                "id", REPOSITORY_ID + 1
            ),
            "head_repo": lambda row: row["head"].__setitem__("repo", None),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                row = copy.deepcopy(exact_row())
                mutate(row)
                with self.assertRaises(MODULE.ContractError):
                    self.select([row])

    def test_old_merge_commit_association_is_not_an_authority_input(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn('commits/{source_sha}/pulls', source)
        self.assertIn('"state": "closed"', source)
        self.assertIn('"base": "main"', source)
        self.assertIn('"direction": "desc"', source)


if __name__ == "__main__":
    unittest.main()
