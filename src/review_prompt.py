from typing import List

from .types import ChatMessageDict, GitDiffChange


def format_file_header(change: GitDiffChange) -> str:
    """변경된 파일의 메타데이터(경로, 상태)를 기반으로 사람이 읽기 좋은 헤더를 생성한다."""
    old_path = change.get("old_path")
    new_path = change.get("new_path")

    # GitLab/GitHub API 플래그 확인 (없을 경우 경로 비교로 추론)
    is_new = change.get("new_file", False)
    is_deleted = change.get("deleted_file", False)
    is_renamed = change.get("renamed_file", False) or (
        old_path and new_path and old_path != new_path
    )

    if is_new:
        return f"🆕 **NEW FILE**: `{new_path}`"
    if is_deleted:
        return f"🗑️ **DELETED**: `{old_path}`"
    if is_renamed:
        return f"🚚 **RENAMED**: `{old_path}` ➡️ `{new_path}`"

    # 일반적인 수정 (경로 변경 없음)
    return f"📝 **MODIFIED**: `{new_path}`"


def generate_review_prompt(changes: List[GitDiffChange]) -> List[ChatMessageDict]:
    """Git 변경 사항 리스트를 LLM 리뷰용 messages 포맷으로 변환한다."""

    # 1. Diff 데이터 전처리 (파일 상태 및 코드 블록 포맷팅)
    formatted_changes: List[str] = []
    for change in changes:
        header = format_file_header(change)
        diff_content = change.get("diff", "")

        # 내용이 없거나 바이너리 등의 경우에 대한 기본 메시지
        if not str(diff_content).strip():
            diff_content = "(No content changes or binary file)"

        formatted_changes.append(f"{header}\n```diff\n{diff_content}\n```")

    changes_string = "\n\n".join(formatted_changes)

    # 2. 시스템 프롬프트: 역할 및 출력 형식 정의
    system_instruction = (
        "You are a **Senior Software Engineer & Code Reviewer**.\n"
        "Your goal is to ensure code quality, security, and maintainability.\n\n"
        "**Output Guidelines:**\n"
        "1. **Language**: Provide the full review in **Korean** first.\n"
        "2. **Separator**: Output a single line with '---'.\n"
        "3. **Translation**: Provide the English translation after the separator.\n"
        "4. **Format**: Use GitLab Markdown (bullet points, bold text, code blocks).\n"
    )

    # 3. 사용자 프롬프트: 실제 데이터와 구체적인 리뷰 기준 전달
    review_criteria = """
    **Review Checklist:**
    1.  **🔍 Summary (요약)**: Briefly summarize the changes (Changelog style).
    2.  **🧹 Code Quality (코드 품질)**: 
        - Are naming conventions and type hints used correctly?
        - Is the code readable? Any duplicate logic?
    3.  **🐛 Bugs & Logic (버그 및 로직)**: 
        - Check for logical errors, edge cases, or broken functionality due to refactoring.
        - Pay attention to path changes if files were renamed/deleted.
    4.  **🛡️ Security (보안 - Critical)**: 
        - Check for `verify=False`, hardcoded credentials, or warning suppressions.
        - Are exceptions handled safely?
    5.  **💡 Suggestions**: actionable improvements.
    """

    messages: List[ChatMessageDict] = [
        {
            "role": "system",
            "content": system_instruction,
        },
        {
            "role": "user",
            "content": f"Review the following git diffs:\n\n{changes_string}\n\n{review_criteria}",
        },
    ]

    return messages
