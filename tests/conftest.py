import os

from dotenv import load_dotenv


# 테스트 실행 시 프로젝트 루트의 .env를 로드해서,
# OpenAI / GitLab 등 외부 연동에 필요한 환경변수를 자동으로 주입한다.
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")

# 파일이 존재하지 않으면 조용히 넘어간다.
load_dotenv(dotenv_path=ENV_PATH, override=False)
