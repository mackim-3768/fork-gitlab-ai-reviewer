# AI Code Reviewer

AI Code Reviewer는 GitLab 저장소의 코드 변경 사항을 **자동으로 리뷰**해 주는 Flask 기반 웹 애플리케이션입니다.
GitLab Webhook(머지 요청 및 푸시 이벤트)을 받아 diff를 조회하고, OpenAI(또는 Azure OpenAI)를 사용해 코드 리뷰 코멘트를 생성한 뒤, GitLab에 **마크다운 형식의 댓글**로 남깁니다.

---

## 개요

- GitLab에서 발생하는 다음 이벤트를 처리합니다.
  - 머지 요청 이벤트(`object_kind = "merge_request"`, action: `open`인 경우만 처리)
  - 푸시 이벤트(`object_kind = "push"`)
- 각 이벤트에 대해 GitLab API로 diff를 조회한 뒤, OpenAI ChatCompletion API에 전달하여 리뷰를 생성합니다.
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
2. 헤더 `X-Gitlab-Token` 값을 `EXPECTED_GITLAB_TOKEN` 환경 변수와 비교하여 인증
3. 아래 GitLab API로 MR diff 조회

   ```text
   GET {GITLAB_URL}/projects/{project_id}/merge_requests/{mr_iid}/changes
   ```

4. 응답에서 `changes[].diff`를 추출해 하나의 문자열로 합침
5. 리뷰 프롬프트(질문 목록 포함)를 구성하고 `openai.ChatCompletion.create(...)` 호출
6. 생성된 리뷰를 아래 API로 MR 댓글로 등록

   ```text
   POST {GITLAB_URL}/projects/{project_id}/merge_requests/{mr_iid}/notes
   ```

### 2. 푸시(Push) / 커밋 플로우

1. GitLab에서 푸시 이벤트 발생 시 Webhook 호출
2. 헤더 토큰을 동일하게 검증
3. 아래 GitLab API로 커밋 diff 조회

   ```text
   GET {GITLAB_URL}/projects/{project_id}/repository/commits/{commit_id}/diff
   ```

4. diff 목록을 문자열로 합쳐 프롬프트에 포함
5. `openai.ChatCompletion.create(...)`로 리뷰 생성
6. 생성된 리뷰를 아래 API로 커밋 댓글로 등록

   ```text
   POST {GITLAB_URL}/projects/{project_id}/repository/commits/{commit_id}/comments
   ```

오류가 발생하면 콘솔에 예외를 출력하고, GitLab 댓글에 에러 메시지를 포함한 안내 문구를 남깁니다.

---

## 요구 사항

- Python **3.8 이상** (예제 Docker 이미지 기준 3.9 사용)
- GitLab 프로젝트 1개 이상 (Webhook 설정 권한 필요)
- OpenAI 또는 Azure OpenAI API Key
- GitLab Personal Access Token (API 권한 포함)
- Docker 및 docker-compose (선택, 컨테이너 실행용)

Python 의존성은 `requirements.txt`에 정의되어 있습니다.

---

## 설치 (로컬 실행)

### 1. 저장소 클론

```bash
git clone git@github.com:dhkimxx/OpenAI-Gitlab-PR-Review.git
cd OpenAI-Gitlab-PR-Review
```

### 2. (선택) 가상환경 생성 및 활성화

```bash
python -m venv .venv
source .venv/bin/activate  # macOS / Linux
# .venv\Scripts\activate  # Windows
```

### 3. 의존성 설치

```bash
pip install -r requirements.txt
```

---

## 환경 변수 설정

이 애플리케이션은 모든 설정을 **환경 변수**로 받습니다. 루트 디렉터리에 `.env` 파일을 두고 관리하거나, 쉘에서 직접 export 해도 됩니다.

### 필수 환경 변수

- `OPENAI_API_KEY`  
  OpenAI 또는 Azure OpenAI API Key

- `OPENAI_API_MODEL`

  - OpenAI 사용 시: 모델 이름 (예: `gpt-3.5-turbo`)
  - Azure OpenAI 사용 시: **배포 이름(deployment name)** 이며 `deployment_id`와 `model` 파라미터에 함께 사용됩니다.

- `GITLAB_TOKEN`  
  GitLab Personal Access Token. MR 조회 및 댓글 작성이 가능하도록 `api` 스코프 권장.

- `GITLAB_URL`  
  GitLab API 베이스 URL. GitLab.com의 경우:

  ```text
  https://gitlab.com/api/v4
  ```

  self-hosted GitLab을 사용하는 경우 인스턴스 주소에 맞게 변경합니다.

- `EXPECTED_GITLAB_TOKEN`  
  Webhook 보안을 위한 GitLab **Secret Token** 값입니다. GitLab Webhook 설정 화면에서 입력한 값과 동일해야 합니다.
  강력한 랜덤 토큰을 생성하기 위해 아래와 같은 명령어(macOS / Linux 기준) 사용을 권장합니다.

  ```bash
  openssl rand -base64 32
  ```

### 선택 환경 변수 (Azure OpenAI 사용 시)

- `AZURE_OPENAI_API_BASE`  
  Azure OpenAI 엔드포인트, 예:

  ```text
  https://YOUR-RESOURCE-NAME.openai.azure.com/
  ```

- `AZURE_OPENAI_API_VERSION`  
  API 버전, 예:

  ```text
  2023-05-15
  ```

두 값이 설정되면 애플리케이션은 `openai.api_type = "azure"`를 사용하도록 자동 구성됩니다.

### `.env` 예시

```env
OPENAI_API_KEY=your-openai-api-key
OPENAI_API_MODEL=gpt-3.5-turbo

GITLAB_TOKEN=your-gitlab-personal-access-token
GITLAB_URL=https://gitlab.com/api/v4

EXPECTED_GITLAB_TOKEN=your-webhook-secret-token

AZURE_OPENAI_API_BASE= # optional
AZURE_OPENAI_API_VERSION= # optional
```

---

## 실행 방법

### 1. 로컬 개발 서버 실행

`main.py`는 Flask 개발 서버를 직접 실행합니다.

```bash
python main.py
```

- Host: `0.0.0.0`
- Port: `8080`
- Webhook 엔드포인트 예시:

  ```text
  http://localhost:8080/webhook
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

- 컨테이너 내부 포트: `80`
- `docker-compose.yaml` 포트 매핑:

  ```yaml
  ports:
    - "9655:80"
  ```

따라서 외부에서 접근하는 Webhook URL은 다음과 같습니다.

```text
http://localhost:9655/webhook
```

컨테이너 내부에서는 다음 커맨드로 애플리케이션이 실행됩니다.

```bash
gunicorn --bind 0.0.0.0:80 main:app
```

---

## GitLab Webhook 설정

GitLab 프로젝트에서 Webhook을 아래와 같이 설정합니다.

1. 프로젝트 메뉴에서 `Settings` → `Webhooks`로 이동합니다.
2. **URL** 입력:

   - 로컬 개발 (Flask 개발 서버):

     ```text
     http://YOUR-HOST:8080/webhook
     ```

   - Docker (docker-compose 사용):

     ```text
     http://YOUR-HOST:9655/webhook
     ```

3. **Secret token** 입력:

   - `.env`에 설정한 `EXPECTED_GITLAB_TOKEN`과 **동일한 값**을 입력합니다.

4. Trigger 이벤트 선택:

   - ✅ `Merge requests events`
   - ✅ `Push events`

5. (선택) Webhook 화면에서 `Test` 버튼을 사용해 푸시/머지 요청 이벤트를 테스트할 수 있습니다.

토큰이 일치하지 않으면 애플리케이션은 `403 Unauthorized`를 반환합니다.

---

## 동작 방식 요약 (프롬프트)

각 이벤트 처리 시 애플리케이션은:

1. GitLab에서 diff를 조회해 하나의 문자열로 합칩니다.
2. "구조, 보안, 가독성" 등에 초점을 둔 프롬프트와 질문 목록을 구성합니다.
3. `openai.ChatCompletion.create(...)`에 아래와 유사한 설정으로 요청합니다.
   - `deployment_id = OPENAI_API_MODEL`
   - `model = OPENAI_API_MODEL` 또는 기본값 `gpt-3.5-turbo`
4. 응답 내용을 정리해 GitLab에 마크다운 댓글로 등록합니다.

에러 발생 시:

- 콘솔에 예외를 출력합니다.
- GitLab 댓글에는 “지금은 사람이 리뷰해야 한다”는 안내와 함께 에러 메시지를 포함합니다.

---

## 문제 해결 (Troubleshooting)

- **403 Unauthorized 발생**

  - GitLab Webhook 설정의 **Secret token**이 `EXPECTED_GITLAB_TOKEN`과 같은지 확인합니다.
  - Webhook 요청이 올바른 URL/포트(`/webhook`)로 가고 있는지 확인합니다.

- **머지 요청/커밋에 리뷰 댓글이 안 달리는 경우**

  - GitLab Webhook 화면의 "Recent Deliveries"에서 이벤트가 실제로 전송되었는지 확인합니다.
  - 컨테이너/애플리케이션 로그에 에러가 없는지 확인합니다.
  - `GITLAB_TOKEN`에 충분한 권한이 있는지, `GITLAB_URL`이 올바른지 점검합니다.

- **OpenAI 관련 에러**
  - `OPENAI_API_KEY`, `OPENAI_API_MODEL` 값이 유효한지 확인합니다.
  - Azure OpenAI 사용 시에는 다음 값들을 다시 확인합니다.
    - `AZURE_OPENAI_API_BASE`
    - `AZURE_OPENAI_API_VERSION`
    - 배포 이름(`OPENAI_API_MODEL`)

---

## 한계 및 주의사항

- 머지 요청의 경우 `action = "open"`인 이벤트만 처리합니다. 이후 업데이트/재오픈 이벤트는 기본 코드에서는 무시합니다.
- 매우 큰 diff의 경우 토큰 제한에 걸릴 수 있습니다.
- 이 도구는 **인공지능 보조 도구**일 뿐이며, 최종 리뷰 책임은 항상 사람에게 있습니다. AI가 제안한 내용을 그대로 수용하기보다는 참고 자료로 활용하는 것을 권장합니다.
