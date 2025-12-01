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

    # 2. 시스템 프롬프트: 이중언어(Bilingual) 전문가로 설정
    system_instruction = (
        "You are a **Senior Software Engineer & Bilingual Code Reviewer** (English/Korean).\n"
        "Your goal is to ensure code quality and security while bridging the language gap.\n\n"
        "**Output Guidelines:**\n"
        "1. **Bilingual Mode**: For every section, provide the content in **English first**, followed immediately by the **Korean translation**.\n"
        "2. **Structure**: Follow the requested structure strictly (Verdict -> Critical -> Summary -> Details).\n"
        "3. **Tone**: Professional, objective, and constructive.\n"
    )

    # 3. 사용자 프롬프트: 섹션별 병기(Pair) 포맷 지정
    review_criteria = """
You are an AI code reviewer.  
Your output MUST start immediately with "### 1. 🚦 종합 판정" —  
NO leading characters, NO "---", NO blank lines, NO commentary before that line.

The entire review MUST be structured as follows, in this exact order.

IMPORTANT LANGUAGE RULE:
- First, provide the **full Korean version only** for Sections 1–4.
- After completing all KR sections, provide the **English version for Sections 1–4 again** in full.
- KR and EN must NEVER be mixed within the same section.
- No additional commentary before or after the structure.

ANALYSIS RULE:
- Review ONLY the content inside ```diff blocks.
- Do NOT infer missing code.
- Be strict, concise, deterministic.

<The following is the output format required for the LLM.>

### 1. 🚦 종합 판정
- 판정: [🟢 승인 | 🟡 코멘트 | 🔴 변경 요청]
- 이유(KR): 한 문장 요약

### 2. 🚨 치명적 이슈(Must Fix)
- 치명적 이슈 없으면: "발견되지 않음"
- 있으면 다음 형식:
  - 🚨 [파일경로:줄번호] 이슈 제목
    - 왜 치명적인지 + 수정 권장사항

### 3. 🔍 변경 요약
- 변경사항을 bullet로 요약(KR)

### 4. 🧹 제안 & 스타일
- Nitpicks(사소한 개선)
- Structural(구조적 제안)

----------------------------------------
### After finishing all Korean content above,
output the FULL English version again, in this exact structure:

### 1. 🚦 Review Verdict
- Verdict: …
- Reason (EN): …

### 2. 🚨 Critical Issues (Must Fix)
- "None detected" or list issues

### 3. 🔍 Change Summary
- Bullet-style summary (EN)

### 4. 🧹 Suggestions & Style
- Nitpicks
- Structural suggestions

----------------------------------------

VERDICT RULE:
- 🔴 Request Changes → ONLY if Section 2 has at least one issue
- 🟡 Comment → Section 2 clean BUT Section 4 has meaningful suggestions
- 🟢 Approve → Section 2 clean AND Section 4 suggestions are minor

DO NOT DEVIATE FROM THIS FORMAT.
DO NOT insert extra symbols or separators.
DO NOT mix KR/EN within the same section.
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
