import base64
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "hf_static_space.py"
CORE = ROOT / "scripts" / "hf_static_space_core.py"
SPEC = importlib.util.spec_from_file_location("hf_static_space_postmerge", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

REPOSITORY = "szl-holdings/lambda-gate-holo"
REPOSITORY_ID = 1295931629
BEFORE = "a" * 40
SOURCE = "b" * 40
HEAD = "c" * 40


def exact_row(*, row_id: int = 101, number: int = 7) -> dict:
    return {
        "id": row_id,
        "number": number,
        "state": "closed",
        "merged_at": "2026-08-28T12:00:00Z",
        "merge_commit_sha": SOURCE,
        "base": {
            "ref": "main",
            "sha": BEFORE,
            "repo": {"full_name": REPOSITORY, "id": REPOSITORY_ID},
        },
        "head": {
            "ref": "fix/postmerge-pr-inventory-20260828",
            "sha": HEAD,
            "repo": {"full_name": REPOSITORY, "id": REPOSITORY_ID},
        },
    }


class PostMergeInventoryTests(unittest.TestCase):
    def test_tracked_core_matches_the_pinned_blob(self) -> None:
        value = CORE.read_bytes()
        self.assertEqual(len(value), MODULE._CORE_BLOB_BYTES)
        self.assertEqual(MODULE._git_blob_sha1(value), MODULE._CORE_BLOB_SHA)

    def test_missing_local_core_bootstraps_anonymous_exact_blob(self) -> None:
        value = CORE.read_bytes()
        document = {
            "sha": MODULE._CORE_BLOB_SHA,
            "encoding": "base64",
            "size": len(value),
            "content": base64.encodebytes(value).decode("ascii"),
        }
        response = io.BytesIO(json.dumps(document).encode("utf-8"))
        with (
            tempfile.TemporaryDirectory() as temporary,
            mock.patch.object(
                MODULE, "_CORE_PATH", Path(temporary) / "not-present.py"
            ),
            mock.patch.object(
                MODULE._bootstrap_url_request,
                "urlopen",
                return_value=response,
            ) as urlopen,
        ):
            self.assertEqual(MODULE._read_pinned_core(), value)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, MODULE._CORE_API_URL)
        self.assertNotIn("Authorization", request.headers)

    def test_tampered_local_core_fails_closed_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "hf_static_space_core.py"
            path.write_bytes(b"tampered\n")
            with (
                mock.patch.object(MODULE, "_CORE_PATH", path),
                mock.patch.object(
                    MODULE._bootstrap_url_request,
                    "urlopen",
                ) as urlopen,
            ):
                with self.assertRaisesRegex(RuntimeError, "pinned blob"):
                    MODULE._read_pinned_core()
            urlopen.assert_not_called()

    def test_closed_inventory_url_is_deterministic(self) -> None:
        self.assertEqual(
            MODULE._closed_pull_inventory_url(
                "https://api.github.example", REPOSITORY
            ),
            (
                "https://api.github.example/repos/"
                f"{REPOSITORY}/pulls?"
                "state=closed&base=main&sort=updated&direction=desc"
            ),
        )

    def test_exact_association_remains_the_fast_path(self) -> None:
        association_url = "https://api.example/association"
        closed_url = "https://api.example/closed"
        expected = [exact_row()]
        calls: list[str] = []

        def delegate(url: str, _token: str, _label: str) -> list[dict]:
            calls.append(url)
            if url == association_url:
                return expected
            raise AssertionError(f"unexpected fallback request: {url}")

        result = MODULE._resolve_merged_pull_inventory(
            association_url,
            closed_url,
            "token",
            "associated pull-request",
            delegate,
            REPOSITORY,
            REPOSITORY_ID,
            BEFORE,
            SOURCE,
        )
        self.assertIs(result, expected)
        self.assertEqual(calls, [association_url])

    def test_wrong_commit_association_falls_back_to_bounded_closed_inventory(self) -> None:
        association_url = "https://api.example/association"
        closed_url = "https://api.example/closed"
        unrelated = exact_row(row_id=1, number=1)
        unrelated["merge_commit_sha"] = "d" * 40
        expected = [unrelated, exact_row(row_id=2, number=2)]
        calls: list[str] = []

        def delegate(url: str, _token: str, _label: str) -> list[dict]:
            calls.append(url)
            if url == association_url:
                return [unrelated]
            if url == closed_url:
                return expected
            raise AssertionError(url)

        result = MODULE._resolve_merged_pull_inventory(
            association_url,
            closed_url,
            "token",
            "associated pull-request",
            delegate,
            REPOSITORY,
            REPOSITORY_ID,
            BEFORE,
            SOURCE,
        )
        self.assertIs(result, expected)
        self.assertEqual(calls, [association_url, closed_url])

    def test_closed_inventory_requires_one_unambiguous_exact_merge(self) -> None:
        association_url = "association"
        closed_url = "closed"
        unrelated = exact_row(row_id=1, number=1)
        unrelated["merge_commit_sha"] = "d" * 40
        cases = {
            "none": [unrelated],
            "two": [
                exact_row(row_id=2, number=2),
                exact_row(row_id=3, number=3),
            ],
        }
        for name, closed_rows in cases.items():
            with self.subTest(name=name):
                def delegate(url: str, _token: str, _label: str) -> list[dict]:
                    return [unrelated] if url == association_url else closed_rows

                with self.assertRaisesRegex(
                    MODULE.ContractError, "unambiguous closed merged PR"
                ):
                    MODULE._resolve_merged_pull_inventory(
                        association_url,
                        closed_url,
                        "token",
                        "associated pull-request",
                        delegate,
                        REPOSITORY,
                        REPOSITORY_ID,
                        BEFORE,
                        SOURCE,
                    )

    def test_hostile_tuple_variants_are_not_exact(self) -> None:
        mutations = {
            "non_object": None,
            "bad_id": {"id": 0},
            "bad_number": {"number": 0},
            "open": {"state": "open"},
            "missing_merged_at": {"merged_at": None},
            "wrong_merge": {"merge_commit_sha": "d" * 40},
            "wrong_base_ref": {"base.ref": "develop"},
            "wrong_base_sha": {"base.sha": "d" * 40},
            "wrong_base_name": {"base.repo.full_name": "other/repo"},
            "wrong_base_id": {"base.repo.id": 1},
            "missing_head_ref": {"head.ref": ""},
            "short_head_sha": {"head.sha": "abc"},
            "wrong_head_name": {"head.repo.full_name": "other/repo"},
            "wrong_head_id": {"head.repo.id": 1},
        }
        for name, mutation in mutations.items():
            with self.subTest(name=name):
                if name == "non_object":
                    row = mutation
                else:
                    row = copy.deepcopy(exact_row())
                    for path, value in mutation.items():
                        target = row
                        parts = path.split(".")
                        for part in parts[:-1]:
                            target = target[part]
                        target[parts[-1]] = value
                self.assertFalse(
                    MODULE._closed_pull_row_is_exact(
                        row, REPOSITORY, REPOSITORY_ID, BEFORE, SOURCE
                    )
                )

    def test_bounded_inventory_rejects_duplicate_identity(self) -> None:
        pages = [
            [{"id": 1}, {"id": 2}],
            [{"id": 2}],
        ]
        with (
            mock.patch.object(MODULE, "GITHUB_PER_PAGE", 2),
            mock.patch.object(MODULE, "GITHUB_MAX_PAGES", 3),
            mock.patch.object(MODULE, "_request_json", side_effect=pages),
        ):
            with self.assertRaisesRegex(
                MODULE.ContractError, "malformed or duplicated"
            ):
                MODULE._CORE_COMPLETE_LIST_INVENTORY(
                    "https://api.example/pulls", "token", "closed pull-request"
                )

    def test_bounded_inventory_rejects_page_cap_exhaustion(self) -> None:
        pages = [
            [{"id": 1}, {"id": 2}],
            [{"id": 3}, {"id": 4}],
        ]
        with (
            mock.patch.object(MODULE, "GITHUB_PER_PAGE", 2),
            mock.patch.object(MODULE, "GITHUB_MAX_PAGES", 2),
            mock.patch.object(MODULE, "_request_json", side_effect=pages),
        ):
            with self.assertRaisesRegex(
                MODULE.ContractError, "bounded pagination limit"
            ):
                MODULE._CORE_COMPLETE_LIST_INVENTORY(
                    "https://api.example/pulls", "token", "closed pull-request"
                )

    def test_bounded_inventory_closes_on_a_short_page(self) -> None:
        pages = [
            [{"id": 2}, {"id": 1}],
            [{"id": 3}],
        ]
        with (
            mock.patch.object(MODULE, "GITHUB_PER_PAGE", 2),
            mock.patch.object(MODULE, "GITHUB_MAX_PAGES", 3),
            mock.patch.object(MODULE, "_request_json", side_effect=pages),
        ):
            result = MODULE._CORE_COMPLETE_LIST_INVENTORY(
                "https://api.example/pulls", "token", "closed pull-request"
            )
        self.assertEqual([row["id"] for row in result], [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
