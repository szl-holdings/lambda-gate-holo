#!/usr/bin/env python3
"""Pinned compatibility entrypoint for governed static-Space publication."""
from __future__ import annotations

import base64 as _bootstrap_base64
import hashlib as _bootstrap_hashlib
import json as _bootstrap_json
from pathlib import Path as _BootstrapPath
import threading as _bootstrap_threading
import urllib.error as _bootstrap_url_error
import urllib.request as _bootstrap_url_request


_CORE_BLOB_SHA = "f20a305b8ae23d12aaed38eca3ca1d3cb0c42e48"
_CORE_BLOB_BYTES = 103144
_CORE_PATH = _BootstrapPath(__file__).with_name("hf_static_space_core.py")
_CORE_API_URL = (
    "https://api.github.com/repos/szl-holdings/lambda-gate-holo/git/blobs/"
    + _CORE_BLOB_SHA
)
_CORE_ENTRYPOINT_MARKER = '\nif __name__ == "__main__":\n'
_EXPECTED_CORE_ENTRYPOINT = """    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"FAIL-CLOSED: {type(error).__name__}: {error}", file=sys.stderr)
        raise SystemExit(1)
"""


def _git_blob_sha1(value: bytes) -> str:
    digest = _bootstrap_hashlib.sha1()
    digest.update(b"blob " + str(len(value)).encode("ascii") + b"\0" + value)
    return digest.hexdigest()


def _read_pinned_core() -> bytes:
    try:
        local = _CORE_PATH.read_bytes()
    except FileNotFoundError:
        local = None
    except OSError as error:
        raise RuntimeError("pinned static-Space core is unreadable") from error

    if local is not None:
        if len(local) != _CORE_BLOB_BYTES or _git_blob_sha1(local) != _CORE_BLOB_SHA:
            raise RuntimeError("tracked static-Space core does not match its pinned blob")
        return local

    request = _bootstrap_url_request.Request(
        _CORE_API_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "szl-hf-static-space-bootstrap/1.0",
            "X-GitHub-Api-Version": "2026-03-10",
        },
    )
    try:
        with _bootstrap_url_request.urlopen(request, timeout=30) as response:
            document = _bootstrap_json.load(response)
    except (
        OSError,
        TimeoutError,
        UnicodeError,
        _bootstrap_url_error.URLError,
        _bootstrap_json.JSONDecodeError,
    ) as error:
        raise RuntimeError("pinned static-Space core bootstrap failed closed") from error

    if (
        not isinstance(document, dict)
        or document.get("sha") != _CORE_BLOB_SHA
        or document.get("encoding") != "base64"
        or document.get("size") != _CORE_BLOB_BYTES
        or not isinstance(document.get("content"), str)
    ):
        raise RuntimeError("pinned static-Space core response is not exact")
    try:
        encoded = "".join(document["content"].split())
        remote = _bootstrap_base64.b64decode(encoded, validate=True)
    except (ValueError, _bootstrap_base64.binascii.Error) as error:
        raise RuntimeError("pinned static-Space core encoding is malformed") from error
    if len(remote) != _CORE_BLOB_BYTES or _git_blob_sha1(remote) != _CORE_BLOB_SHA:
        raise RuntimeError("pinned static-Space core bytes are not exact")
    return remote


_CORE_BYTES = _read_pinned_core()
try:
    _CORE_SOURCE = _CORE_BYTES.decode("utf-8")
except UnicodeDecodeError as error:
    raise RuntimeError("pinned static-Space core is not UTF-8") from error
_CORE_PREFIX, _CORE_SEPARATOR, _CORE_ENTRYPOINT = _CORE_SOURCE.rpartition(
    _CORE_ENTRYPOINT_MARKER
)
if (
    not _CORE_SEPARATOR
    or _CORE_ENTRYPOINT.rstrip("\n") != _EXPECTED_CORE_ENTRYPOINT.rstrip("\n")
):
    raise RuntimeError("pinned static-Space core entrypoint is not exact")
exec(compile(_CORE_PREFIX + "\n", str(_CORE_PATH), "exec"), globals(), globals())

# The wrapper digest transitively binds the core and preserves
# publisher_executable_rebind before any credential-bearing mutation.
_CORE_REQUIRE_GOVERNED_MAIN = require_governed_main
_CORE_COMPLETE_LIST_INVENTORY = _complete_list_inventory
_POSTMERGE_INVENTORY_LOCK = _bootstrap_threading.RLock()


def _closed_pull_inventory_url(api_root: str, repository: str) -> str:
    query = urllib.parse.urlencode(
        (
            ("state", "closed"),
            ("base", "main"),
            ("sort", "updated"),
            ("direction", "desc"),
        )
    )
    return f"{api_root}/repos/{repository}/pulls?{query}"


def _closed_pull_row_is_exact(
    row: object,
    repository: str,
    repository_id: int,
    before_sha: str,
    source_sha: str,
) -> bool:
    if not isinstance(row, dict):
        return False
    base = row.get("base")
    head = row.get("head")
    base_repository = base.get("repo") if isinstance(base, dict) else None
    head_repository = head.get("repo") if isinstance(head, dict) else None
    head_sha = head.get("sha") if isinstance(head, dict) else None
    head_ref = head.get("ref") if isinstance(head, dict) else None
    return (
        type(row.get("id")) is int
        and row["id"] > 0
        and type(row.get("number")) is int
        and row["number"] > 0
        and row.get("state") == "closed"
        and isinstance(row.get("merged_at"), str)
        and bool(row["merged_at"])
        and row.get("merge_commit_sha") == source_sha
        and isinstance(base, dict)
        and base.get("ref") == "main"
        and base.get("sha") == before_sha
        and isinstance(base_repository, dict)
        and base_repository.get("full_name") == repository
        and base_repository.get("id") == repository_id
        and isinstance(head, dict)
        and isinstance(head_ref, str)
        and bool(head_ref)
        and isinstance(head_sha, str)
        and HEX40.fullmatch(head_sha) is not None
        and isinstance(head_repository, dict)
        and head_repository.get("full_name") == repository
        and head_repository.get("id") == repository_id
    )


def _resolve_merged_pull_inventory(
    association_url: str,
    closed_url: str,
    token: str,
    label: str,
    delegate,
    repository: str,
    repository_id: int,
    before_sha: str,
    source_sha: str,
) -> list[dict]:
    associated = delegate(association_url, token, label)
    exact_associated = [
        row
        for row in associated
        if _closed_pull_row_is_exact(
            row, repository, repository_id, before_sha, source_sha
        )
    ]
    if len(exact_associated) == 1:
        return associated

    closed = delegate(
        closed_url,
        token,
        "bounded closed pull-request",
    )
    exact_closed = [
        row
        for row in closed
        if _closed_pull_row_is_exact(
            row, repository, repository_id, before_sha, source_sha
        )
    ]
    if len(exact_closed) != 1:
        raise ContractError(
            "exact main revision is not one unambiguous closed merged PR"
        )
    return closed


def require_governed_main(
    source_sha: str,
    event_path: Path,
    output_path: Path,
    config_path: Path = DEFAULT_CONFIG,
    *,
    failure_output_path: Path | None = None,
) -> dict:
    source_sha = exact_sha(source_sha)
    config = load_config(config_path)
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    api_root = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    event = _load_event(event_path)
    before_sha = exact_sha(event.get("before"), "push before revision")
    repository_id = TARGET_REPOSITORY_IDS.get(repository)
    association_url = f"{api_root}/repos/{repository}/commits/{source_sha}/pulls"
    closed_url = _closed_pull_inventory_url(api_root, repository)

    if repository != config["source_repository"] or repository_id is None:
        return _CORE_REQUIRE_GOVERNED_MAIN(
            source_sha,
            event_path,
            output_path,
            config_path,
            failure_output_path=failure_output_path,
        )

    with _POSTMERGE_INVENTORY_LOCK:
        delegate = globals().get("_complete_list_inventory")
        if not callable(delegate):
            raise ContractError("pull-request inventory reader is unavailable")

        def inventory(url: str, token: str, label: str) -> list[dict]:
            if url != association_url:
                return delegate(url, token, label)
            return _resolve_merged_pull_inventory(
                association_url,
                closed_url,
                token,
                label,
                delegate,
                repository,
                repository_id,
                before_sha,
                source_sha,
            )

        globals()["_complete_list_inventory"] = inventory
        try:
            return _CORE_REQUIRE_GOVERNED_MAIN(
                source_sha,
                event_path,
                output_path,
                config_path,
                failure_output_path=failure_output_path,
            )
        finally:
            globals()["_complete_list_inventory"] = delegate


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"FAIL-CLOSED: {type(error).__name__}: {error}", file=sys.stderr)
        raise SystemExit(1)
