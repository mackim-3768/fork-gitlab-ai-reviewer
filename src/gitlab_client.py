import logging
from typing import Any, Dict, List
from urllib.parse import quote

import requests

from .types import GitDiffChange, MergeRequestChangesResponse


logger = logging.getLogger(__name__)


def get_merge_request_changes(
    api_base_url: str,
    access_token: str,
    project_id: int,
    merge_request_iid: int,
) -> MergeRequestChangesResponse:
    """GitLab에서 특정 MR의 변경 사항(changes)을 조회한다."""

    url = f"{api_base_url}/projects/{project_id}/merge_requests/{merge_request_iid}/changes"
    headers = {"Private-Token": access_token}

    response = requests.get(url, headers=headers)
    logger.info(
        "Fetched merge_request changes: url=%s, status_code=%s",
        url,
        response.status_code,
    )

    return response.json()


def post_merge_request_comment(
    api_base_url: str,
    access_token: str,
    project_id: int,
    merge_request_iid: int,
    body: str,
) -> None:
    """GitLab MR에 리뷰 코멘트를 남긴다."""

    url = (
        f"{api_base_url}/projects/{project_id}/merge_requests/{merge_request_iid}/notes"
    )
    headers = {"Private-Token": access_token}
    payload = {"body": body}

    response = requests.post(url, headers=headers, json=payload)
    logger.info(
        "Posted merge_request review comment: project_id=%s, mr_id=%s, status_code=%s",
        project_id,
        merge_request_iid,
        response.status_code,
    )


def get_commit_diff(
    api_base_url: str,
    access_token: str,
    project_id: int,
    commit_id: str,
) -> List[GitDiffChange]:
    """GitLab에서 특정 커밋의 diff를 조회한다."""

    url = f"{api_base_url}/projects/{project_id}/repository/commits/{commit_id}/diff"
    headers = {"Private-Token": access_token}

    response = requests.get(url, headers=headers)
    logger.info(
        "Fetched commit diff: url=%s, status_code=%s",
        url,
        response.status_code,
    )

    return response.json()


def post_commit_comment(
    api_base_url: str,
    access_token: str,
    project_id: int,
    commit_id: str,
    note: str,
) -> None:
    """GitLab 커밋에 리뷰 코멘트를 남긴다."""

    url = (
        f"{api_base_url}/projects/{project_id}/repository/commits/{commit_id}/comments"
    )
    headers = {"Private-Token": access_token}
    payload = {"note": note}

    response = requests.post(url, headers=headers, json=payload)
    logger.info(
        "Posted commit review comment: project_id=%s, commit_id=%s, status_code=%s",
        project_id,
        commit_id,
        response.status_code,
    )


def get_repository_file_raw(
    api_base_url: str,
    access_token: str,
    project_id: int,
    file_path: str,
    ref: str,
) -> str:
    """GitLab 저장소에서 특정 ref 기준 파일 raw 본문을 조회한다."""

    encoded_path = quote(file_path, safe="")
    url = f"{api_base_url}/projects/{project_id}/repository/files/{encoded_path}/raw"
    headers = {"Private-Token": access_token}
    params = {"ref": ref}

    response = requests.get(url, headers=headers, params=params)
    logger.info(
        "Fetched repository file raw: project_id=%s, ref=%s, path=%s, status_code=%s",
        project_id,
        ref,
        file_path,
        response.status_code,
    )
    response.raise_for_status()
    return response.text
