from src.boy_scout_service import _collect_candidate_paths, _truncate_text


def test_collect_candidate_paths_filters_deleted_non_code_and_duplicates() -> None:
    changes = [
        {"new_path": "src/a.py", "deleted_file": False},
        {"new_path": "src/a.py", "deleted_file": False},
        {"new_path": "docs/readme.md", "deleted_file": False},
        {"new_path": "src/b.ts", "deleted_file": False},
        {"new_path": "src/deleted.py", "deleted_file": True},
        {"new_path": "Dockerfile", "deleted_file": False},
    ]

    paths = _collect_candidate_paths(changes, max_files=10)

    assert paths == ["src/a.py", "src/b.ts", "Dockerfile"]


def test_collect_candidate_paths_respects_max_files() -> None:
    changes = [
        {"new_path": "a.py", "deleted_file": False},
        {"new_path": "b.py", "deleted_file": False},
        {"new_path": "c.py", "deleted_file": False},
    ]

    paths = _collect_candidate_paths(changes, max_files=2)
    assert paths == ["a.py", "b.py"]


def test_truncate_text() -> None:
    clipped, truncated = _truncate_text("abcdef", max_chars=4)
    assert clipped == "abcd"
    assert truncated is True

    clipped2, truncated2 = _truncate_text("abcd", max_chars=10)
    assert clipped2 == "abcd"
    assert truncated2 is False
