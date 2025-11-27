from typing import List, NotRequired, TypedDict


class GitDiffChange(TypedDict, total=False):
    """GitLab diff 엔트리 중 이 프로젝트에서 실제로 사용하는 필드 정의.

    GitLab API 응답에는 이외에도 다양한 필드가 포함될 수 있지만,
    여기서는 프롬프트/리뷰에 필요한 최소 필드만 모델링한다.
    """

    old_path: str
    new_path: str
    new_file: bool
    deleted_file: bool
    renamed_file: bool
    diff: str


class MergeRequestChangesResponse(TypedDict, total=False):
    """MR changes API 응답에서 사용하는 부분만을 표현한 타입."""

    changes: List[GitDiffChange]


class ChatMessageDict(TypedDict):
    """LLM에 전달하는 단일 메시지 구조 (OpenAI 스타일)."""

    role: str
    content: str
