"""
환경 설정 모듈
.env 파일에서 환경 변수를 로드합니다.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 프로젝트 루트 디렉토리
ROOT_DIR = Path(__file__).parent.parent.parent

# .env 파일 로드
env_path = ROOT_DIR / ".env"
load_dotenv(dotenv_path=env_path)

# Gemini API Key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# 데이터 경로
JSONS_DIR = ROOT_DIR / "jsons"
DEFAULT_DATA_FILES = [
    JSONS_DIR / "2024.json",
    JSONS_DIR / "2025.json"
]

def get_api_key() -> str:
    """Gemini API Key를 반환합니다."""
    return GEMINI_API_KEY

def get_default_data_files() -> list:
    """디폴트 데이터 파일 경로 목록을 반환합니다."""
    return DEFAULT_DATA_FILES
