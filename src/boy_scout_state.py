import logging
import os
import sqlite3
from typing import Optional


logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = "data/boy_scout_state.db"
_DB_ENV_NAME = "BOY_SCOUT_STATE_DB_PATH"


def _get_db_path() -> str:
    value = os.environ.get(_DB_ENV_NAME)
    if value and value.strip():
        return value.strip()
    return _DEFAULT_DB_PATH


def _get_connection() -> sqlite3.Connection:
    path = _get_db_path()
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS boy_scout_review_state (
            project_id INTEGER NOT NULL,
            merge_request_iid INTEGER NOT NULL,
            status TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (project_id, merge_request_iid)
        )
        """
    )
    return conn


def try_claim_boy_scout_review(project_id: int, merge_request_iid: int) -> bool:
    """해당 MR에 대해 보이스카웃 리뷰 슬롯을 선점한다.

    이미 queued/completed 상태가 있으면 False를 반환한다.
    """

    conn: sqlite3.Connection | None = None
    try:
        conn = _get_connection()
        conn.execute(
            """
            INSERT INTO boy_scout_review_state (project_id, merge_request_iid, status, updated_at)
            VALUES (?, ?, 'queued', datetime('now'))
            """,
            (project_id, merge_request_iid),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    except Exception:
        logger.exception("Failed to claim boy scout review slot")
        return False
    finally:
        if conn is not None:
            conn.close()


def mark_boy_scout_review_completed(project_id: int, merge_request_iid: int) -> None:
    """보이스카웃 리뷰를 완료 상태로 마킹한다."""

    conn: sqlite3.Connection | None = None
    try:
        conn = _get_connection()
        conn.execute(
            """
            UPDATE boy_scout_review_state
            SET status = 'completed', updated_at = datetime('now')
            WHERE project_id = ? AND merge_request_iid = ?
            """,
            (project_id, merge_request_iid),
        )
        conn.commit()
    except Exception:
        logger.exception("Failed to mark boy scout review as completed")
    finally:
        if conn is not None:
            conn.close()


def release_boy_scout_review_claim(project_id: int, merge_request_iid: int) -> None:
    """선점된 queued 상태를 해제한다.

    completed 상태는 유지해 중복 코멘트를 방지한다.
    """

    conn: sqlite3.Connection | None = None
    try:
        conn = _get_connection()
        conn.execute(
            """
            DELETE FROM boy_scout_review_state
            WHERE project_id = ? AND merge_request_iid = ? AND status = 'queued'
            """,
            (project_id, merge_request_iid),
        )
        conn.commit()
    except Exception:
        logger.exception("Failed to release boy scout review claim")
    finally:
        if conn is not None:
            conn.close()


def get_boy_scout_review_status(
    project_id: int, merge_request_iid: int
) -> Optional[str]:
    """테스트/디버깅용 상태 조회."""

    conn: sqlite3.Connection | None = None
    try:
        conn = _get_connection()
        cursor = conn.execute(
            """
            SELECT status
            FROM boy_scout_review_state
            WHERE project_id = ? AND merge_request_iid = ?
            """,
            (project_id, merge_request_iid),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return str(row[0])
    except Exception:
        logger.exception("Failed to read boy scout review status")
        return None
    finally:
        if conn is not None:
            conn.close()
