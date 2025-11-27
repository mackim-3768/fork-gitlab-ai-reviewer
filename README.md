# Gitlab AI Code Reviewer

Gitlab AI Code Reviewer는 GitLab 저장소의 코드 변경 사항을 **자동으로 리뷰**해 주는 Flask 기반 웹 애플리케이션입니다.
GitLab Webhook(머지 요청 및 푸시 이벤트)을 받아 diff를 조회하고, OpenAI를 사용해 코드 리뷰 코멘트를 생성한 뒤, GitLab에 **마크다운 형식의 댓글**로 남깁니다.

---

## 개요

- GitLab에서 발생하는 다음 이벤트를 처리합니다.
  - 머지 요청 이벤트(`object_kind = "merge_request"`, action: `open`인 경우만 처리)
  - 푸시 이벤트(`object_kind = "push"`)
- 각 이벤트에 대해 GitLab API로 diff를 조회한 뒤, OpenAI ChatCompletion API(파이썬 SDK v1 기준 `OpenAI` 클라이언트)를 통해 리뷰를 생성합니다.
- 생성된 리뷰를 다음 위치에 댓글로 남깁니다.
  - 머지 요청: MR Note
  - 커밋: Commit Comment

애플리케이션은 단일 HTTP 엔드포인트를 제공합니다.

- `POST /webhook`

GitLab Webhook은 이 엔드포인트로 이벤트를 전송해야 합니다.

---

## 주요 기능

- GitLab 코드 변경 사항 자동 리뷰
- 코드 가독성, 구조, 복잡도, 잠재적 버그 및 보안 이슈에 대한 피드백
- GitLab에서 바로 읽기 좋은 **마크다운 형식**의 코멘트 생성
- 머지 요청과 푸시(커밋)에 모두 대응

---

## 내부 동작 흐름

### 1. 머지 요청(Merge Request) 플로우

1. GitLab에서 MR이 **open** 상태로 생성되면 Webhook 호출
2. 헤더 `X-Gitlab-Token` 값을 `GITLAB_WEBHOOK_SECRET_TOKEN` 환경 변수와 비교하여 인증
3. 아래 GitLab API로 MR diff 조회

   ```text
   GET {GITLAB_URL}/api/v4/projects/{project_id}/merge_requests/{mr_iid}/changes
   ```

4. 응답에서 `changes[].diff`를 추출해 하나의 문자열로 합침
5. 리뷰 프롬프트(질문 목록 포함)를 구성하고 OpenAI Python SDK v1의 `client.chat.completions.create(...)`를 호출
6. 생성된 리뷰를 아래 API로 MR 댓글로 등록

   ```text
   POST {GITLAB_URL}/api/v4/projects/{project_id}/merge_requests/{mr_iid}/notes
   ```

### 2. 푸시(Push) / 커밋 플로우

1. GitLab에서 푸시 이벤트 발생 시 Webhook 호출
2. 헤더 토큰을 동일하게 검증
3. 아래 GitLab API로 커밋 diff 조회

   ```text
   GET {GITLAB_URL}/api/v4/projects/{project_id}/repository/commits/{commit_id}/diff
   ```

4. diff 목록을 문자열로 합쳐 프롬프트에 포함
5. OpenAI Python SDK v1의 `client.chat.completions.create(...)`로 리뷰 생성
6. 생성된 리뷰를 아래 API로 커밋 댓글로 등록

   ```text
   POST {GITLAB_URL}/api/v4/projects/{project_id}/repository/commits/{commit_id}/comments
   ```

오류가 발생하면 콘솔에 예외를 출력하고, GitLab 댓글에 에러 메시지를 포함한 안내 문구를 남깁니다.

---

## 요구 사항

- Python **3.8 이상** (예제 Docker 이미지 기준 3.9 사용)
- GitLab 프로젝트 1개 이상 (Webhook 설정 권한 필요)
- OpenAI API Key
- GitLab Personal Access Token (API 권한 포함)
- Docker 및 docker-compose (선택, 컨테이너 실행용)

Python 의존성은 `requirements.txt`에 정의되어 있습니다.

---

## 환경 변수 설정

이 애플리케이션은 모든 설정을 **환경 변수**로 받습니다. 루트 디렉터리에 `.env` 파일을 두고 관리하거나, 쉘에서 직접 export 해도 됩니다.

### 필수 환경 변수

- `OPENAI_API_KEY`  
  OpenAI API Key

- `OPENAI_API_MODEL`  
  사용할 OpenAI ChatCompletion 모델 이름 (예: `gpt-5.1-mini`)

- `GITLAB_ACCESS_TOKEN`  
  GitLab Personal Access Token. MR 조회 및 댓글 작성이 가능하도록 `api` 스코프 권장.

- `GITLAB_URL`  
  GitLab 인스턴스 **베이스 URL**(프로토콜 + 호스트까지)입니다. GitLab.com의 경우:

  ```text
  https://gitlab.com
  ```

  self-hosted GitLab을 사용하는 경우 예시는 다음과 같습니다.

  ```text
  http://localhost:8080
  ```

  애플리케이션은 내부에서 이 값에 `/api/v4`를 자동으로 붙여 GitLab API를 호출합니다.

- `GITLAB_WEBHOOK_SECRET_TOKEN`  
  Webhook 보안을 위한 GitLab **Secret Token** 값입니다. GitLab Webhook 설정 화면에서 입력한 값과 동일해야 합니다.
  강력한 랜덤 토큰을 생성하기 위해 아래와 같은 명령어(macOS / Linux 기준) 사용을 권장합니다.

  ```bash
  openssl rand -base64 32
  ```

### 선택 환경 변수 (공통)

- `LOG_LEVEL`  
  애플리케이션 전역 로그 레벨을 설정합니다. 설정하지 않으면 `INFO`가 기본값입니다.  
  사용 가능한 값 예: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.

- `ENABLE_MERGE_REQUEST_REVIEW`  
  `merge_request` 이벤트를 처리할지 여부를 제어합니다. 설정하지 않으면 기본값은 `true`입니다.  
  값이 `1`, `true`, `yes`, `on`(대소문자 무시) 중 하나이면 활성화되고, 그 외 값은 비활성화로 간주됩니다.

- `ENABLE_PUSH_REVIEW`  
  `push` 이벤트(커밋) 를 처리할지 여부를 제어합니다. 설정하지 않으면 기본값은 `true`입니다.  
  값이 `1`, `true`, `yes`, `on`(대소문자 무시) 중 하나이면 활성화되고, 그 외 값은 비활성화로 간주됩니다.

### `.env` 예시

```env
OPENAI_API_KEY=your-openai-api-key
OPENAI_API_MODEL=gpt-5.1-mini

GITLAB_ACCESS_TOKEN=your-gitlab-personal-access-token
GITLAB_URL=https://gitlab.com

GITLAB_WEBHOOK_SECRET_TOKEN=your-webhook-secret-token

LOG_LEVEL=INFO

ENABLE_MERGE_REQUEST_REVIEW=true
ENABLE_PUSH_REVIEW=true

# (옵션) 통합 테스트용 GitLab 설정
# GITLAB_TEST_PROJECT_ID=123
# GITLAB_TEST_MERGE_REQUEST_IID=1
# GITLAB_TEST_COMMIT_ID=abcdef1234567890
```

### 테스트 환경(.env) 및 pytest

- 루트 디렉터리의 `.env` 파일은 `tests/conftest.py` 에서 `python-dotenv` 로 자동 로드됩니다.
- `tests/test_openai_service_env.py`, `tests/test_gitlab_client_env.py` 는 실제 OpenAI / GitLab API를 호출하는 **통합 테스트**이며, 다음 조건에서만 실행됩니다.
  - `OPENAI_API_KEY` 가 설정되어 있어야 합니다.
  - GitLab 통합 테스트의 경우:
    - `GITLAB_URL`
    - `GITLAB_ACCESS_TOKEN`
    - `GITLAB_TEST_PROJECT_ID`
    - `GITLAB_TEST_MERGE_REQUEST_IID`
    - `GITLAB_TEST_COMMIT_ID`
- 위 환경변수가 설정되지 않은 경우, 해당 테스트는 `pytest.skip` 으로 자동 건너뜁니다.

테스트 실행 예시는 다음과 같습니다.

- 전체 테스트 실행:
  ```bash
  python -m pytest
  ```
- 통합 테스트만 선택 실행:
  ```bash
  python -m pytest -m integration
  ```

---

## 실행 방법

### 1. 로컬 개발 서버 실행

`main.py`는 Flask 개발 서버를 직접 실행합니다.

```bash
python main.py
```

- Host: `0.0.0.0`
- Port: `9655`
- Webhook 엔드포인트 예시:

  ```text
  http://localhost:9655/webhook
  ```

개발/테스트 용도로 적합하며, 운영 환경에서는 아래 Docker + gunicorn 사용을 권장합니다.

### 2. Docker + docker-compose로 실행 (권장)

이 저장소에는 `Dockerfile`과 `docker-compose.yaml`이 포함되어 있습니다.

1. 프로젝트 루트에 `.env` 파일이 있는지 확인합니다.
2. Docker 이미지 빌드:

   ```bash
   docker-compose build
   ```

3. 컨테이너 실행:

   ```bash
   docker-compose up -d
   ```

기본 설정은 다음과 같습니다.

- 컨테이너 내부 포트: `9655`
- `docker-compose.yaml` 포트 매핑:

  ```yaml
  ports:
    - "9655:9655"
  ```

따라서 외부에서 접근하는 Webhook URL은 다음과 같습니다.

```text
http://localhost:9655/webhook
```

컨테이너 내부에서는 다음 커맨드로 애플리케이션이 실행됩니다.

```bash
gunicorn --bind 0.0.0.0:9655 main:app
```

---

## GitLab Webhook 설정

GitLab 프로젝트에서 Webhook을 아래와 같이 설정합니다.

1. 프로젝트 메뉴에서 `Settings` → `Webhooks`로 이동합니다.
2. **URL** 입력:

   - 로컬 개발 (Flask 개발 서버):

     ```text
     http://YOUR-HOST:9655/webhook
     ```

   - Docker (docker-compose 사용):

     ```text
     http://YOUR-HOST:9655/webhook
     ```

3. **Secret token** 입력:

   - `.env`에 설정한 `GITLAB_WEBHOOK_SECRET_TOKEN`과 **동일한 값**을 입력합니다.

4. Trigger 이벤트 선택:

   - ✅ `Merge requests events`
   - ✅ `Push events`

5. (선택) Webhook 화면에서 `Test` 버튼을 사용해 푸시/머지 요청 이벤트를 테스트할 수 있습니다.

토큰이 일치하지 않으면 애플리케이션은 `403 Unauthorized`를 반환합니다.

---

## 동작 방식 요약 (프롬프트)

각 이벤트 처리 시 애플리케이션은:

1. GitLab에서 diff를 조회해 하나의 문자열로 합칩니다.
2. 파일 상태(추가/삭제/리네임/수정)를 포함해 diff를 파일 단위로 정리하고, 시니어 코드 리뷰어 역할과 체크리스트(요약, 코드 품질, 버그/로직, 보안, 제안)를 담은 프롬프트를 구성합니다. 이때 LLM이 먼저 **한국어 리뷰**, 이어서 `---` 한 줄, 그리고 **동일 구조의 영어 리뷰**를 생성하도록 지시합니다.
3. OpenAI Python SDK v1 기준 `client.chat.completions.create(...)`에 아래와 유사한 설정으로 요청합니다.
   - `model = OPENAI_API_MODEL` 또는 기본값 `gpt-5.1-mini`
4. 응답 내용을 정리해 GitLab에 마크다운 댓글로 등록합니다.

에러 발생 시:

- 콘솔에 예외를 출력합니다.
- GitLab 댓글에는 “지금은 사람이 리뷰해야 한다”는 안내와 함께 에러 메시지를 포함합니다.

---

## 문제 해결 (Troubleshooting)

- **403 Unauthorized 발생**

  - GitLab Webhook 설정의 **Secret token**이 `GITLAB_WEBHOOK_SECRET_TOKEN`과 같은지 확인합니다.
  - Webhook 요청이 올바른 URL/포트(`/webhook`)로 가고 있는지 확인합니다.

- **머지 요청/커밋에 리뷰 댓글이 안 달리는 경우**

  - GitLab Webhook 화면의 "Recent Deliveries"에서 이벤트가 실제로 전송되었는지 확인합니다.
  - 컨테이너/애플리케이션 로그에 에러가 없는지 확인합니다.
  - `GITLAB_ACCESS_TOKEN`에 충분한 권한이 있는지, `GITLAB_URL`이 올바른지 점검합니다.

- **OpenAI 관련 에러**
  - `OPENAI_API_KEY`, `OPENAI_API_MODEL` 값이 유효한지 확인합니다.

---

## 한계 및 주의사항

- 머지 요청의 경우 `action = "open"`인 이벤트만 처리합니다. 이후 업데이트/재오픈 이벤트는 기본 코드에서는 무시합니다.
- 매우 큰 diff의 경우 토큰 제한에 걸릴 수 있습니다.
- 이 도구는 **인공지능 보조 도구**일 뿐이며, 최종 리뷰 책임은 항상 사람에게 있습니다. AI가 제안한 내용을 그대로 수용하기보다는 참고 자료로 활용하는 것을 권장합니다.
