from src.boy_scout_state import (
    get_boy_scout_review_status,
    mark_boy_scout_review_completed,
    release_boy_scout_review_claim,
    try_claim_boy_scout_review,
)


def test_try_claim_allows_only_once(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "boy_scout_state_1.db"
    monkeypatch.setenv("BOY_SCOUT_STATE_DB_PATH", str(db_path))

    assert try_claim_boy_scout_review(1, 10) is True
    assert try_claim_boy_scout_review(1, 10) is False
    assert get_boy_scout_review_status(1, 10) == "queued"


def test_release_only_removes_queued(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "boy_scout_state_2.db"
    monkeypatch.setenv("BOY_SCOUT_STATE_DB_PATH", str(db_path))

    assert try_claim_boy_scout_review(2, 20) is True
    release_boy_scout_review_claim(2, 20)
    assert get_boy_scout_review_status(2, 20) is None

    assert try_claim_boy_scout_review(2, 20) is True
    mark_boy_scout_review_completed(2, 20)
    release_boy_scout_review_claim(2, 20)
    assert get_boy_scout_review_status(2, 20) == "completed"
