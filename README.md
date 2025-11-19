# 회계 데이터 분석 & AI 가결산 시스템

회계/재무 JSON 데이터를 분석하고, AI 기반 가결산 및 세금 예측을 제공하는 Streamlit 대시보드입니다.

## 📋 주요 기능

### 1. 가결산 대시보드
- **손익계산서 분석**: 연도별 손익 현황 및 추이 시각화
- **계정과목 분석**: 주요 계정과목별 금액 현황
- **거래처 분석**: 주요 거래처별 거래 금액

### 2. AI 계정 분류 시스템
- **회사 패턴 학습**: 2024년 전년도 거래 데이터 기반 자동 학습
- **자동 추천**: 거래처별 자주 사용한 계정과목 추천 (💡전년도 표시)
- **업종 정보**: 거래처의 업종 정보 자동 표시 (bizcond/bizcate)
- **Gemini AI**: Google Gemini API 활용한 지능형 계정 분류

### 3. 카드 누락 분석
- **전표 상태 필터링**: 미추천/확정/확정가능/삭제전표/불공제 상태별 필터
- **누락 금액 계산**: 확정 전표 기준 카드 내역 누락 금액 자동 계산
- **상세 내역 표시**: 거래처명, 금액, 업종, 전년도 이력 표시

### 4. 세금 예측
- **누진세 계산**: 소득세 누진세율 자동 적용
- **예상 세액**: 현재 손익 기준 예상 세금 계산

### 5. AI 리포트 생성
- **자동 보고서**: Gemini AI 기반 재무 상태 종합 분석 리포트
- **인사이트 제공**: 주요 지표 및 개선 사항 제안

## 🛠️ 기술 스택

- **언어**: Python 3.10+
- **환경 관리**: UV (Python package installer and resolver)
- **웹 프레임워크**: Streamlit
- **데이터 처리**: Pandas
- **시각화**: Plotly
- **AI**: Google Generative AI (Gemini API)
- **환경 변수**: python-dotenv

## 📁 프로젝트 구조

```
no_code_analyse/
├── app.py                    # 메인 Streamlit 대시보드
├── src/
│   ├── app.py               # 재무 데이터 분석 앱
│   └── modules/
│       ├── __init__.py      # 모듈 초기화
│       ├── config.py        # 환경 설정 관리
│       ├── data_loader.py   # JSON 데이터 로딩
│       └── ai_categorizer.py # AI 계정 분류
├── jsons/                   # 원본 JSON 데이터 (2021-2025)
├── jsons2xlsx/              # JSON → XLSX 변환 모듈
├── Preprocessing/           # 데이터 전처리 모듈
├── test/                    # 테스트 디렉토리
├── docs/                    # 문서
├── requirements.txt         # Python 패키지 의존성
├── .env                     # 환경 변수 (API 키 등)
└── README.md               # 프로젝트 문서
```

## 🚀 설치 및 실행

### 1. 환경 설정

```bash
# UV 설치 (macOS/Linux)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 저장소 클론
git clone <repository-url>
cd no_code_analyse

# 가상환경 생성
uv venv

# 가상환경 활성화
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows
```

### 2. 패키지 설치

```bash
# requirements.txt 기반 패키지 설치
uv pip install -r requirements.txt
```

### 3. 환경 변수 설정

`.env` 파일을 생성하고 Gemini API 키를 설정합니다:

```bash
GEMINI_API_KEY=your_gemini_api_key_here
```

### 4. 실행

```bash
# 메인 가결산 대시보드 실행
uv run streamlit run app.py

# 재무 데이터 분석 앱 실행
uv run streamlit run src/app.py
```

브라우저에서 자동으로 열립니다 (일반적으로 `http://localhost:8501`).

## 📖 사용법

### 데이터 준비

1. **기본 데이터**: `jsons/2024.json`, `jsons/2025.json` 파일이 자동으로 로드됩니다
2. **파일 업로드**: 사이드바에서 추가 JSON 파일을 업로드할 수 있습니다

### 대시보드 탐색

#### Tab 1: 손익계산서
- 연도별 손익 현황 확인
- 주요 계정과목별 금액 분석
- 대차대조표/손익계산서 구분

#### Tab 2: 카드 누락 분석
- 전표 상태 선택 (다중 선택 가능)
- 누락된 카드 거래 내역 확인
- 전년도 이력 및 업종 정보 참조

#### Tab 3: AI 리포트
- "AI 리포트 생성하기" 버튼 클릭
- 재무 상태 종합 분석 확인
- AI 추천 사항 검토

### AI 계정 분류

1. 미분류 거래 항목 확인
2. 💡전년도 표시를 참고하여 수동 분류 또는
3. "AI로 계정과목 분류" 버튼 클릭하여 자동 분류

## 🔑 환경 변수

| 변수명 | 설명 | 필수 |
|--------|------|------|
| `GEMINI_API_KEY` | Google Gemini API 키 | ✅ |

## 📊 데이터 구조

JSON 파일은 다음과 같은 한국 회계 데이터 구조를 가집니다:

```json
{
  "cd_acctit": "계정코드",
  "nm_acctit": "계정명",
  "mn_bungae1": "차변 금액",
  "mn_bungae2": "대변 금액",
  "da_date": "날짜",
  "nm_trade": "거래처명",
  "bizcond": "업태",
  "bizcate": "업종",
  "gb_slip": "전표상태"
}
```

## 🤝 기여

이 프로젝트는 한국어 회계 데이터 분석을 위한 오픈소스 프로젝트입니다.

## 📝 라이선스

MIT License

## 🔗 관련 링크

- [Streamlit 문서](https://docs.streamlit.io/)
- [Google Gemini API](https://ai.google.dev/)
- [UV Documentation](https://github.com/astral-sh/uv)

---

**마지막 업데이트**: 2024-11-18
