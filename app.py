import streamlit as st
import os
from dotenv import load_dotenv
import utils  # 같은 폴더의 utils.py
from tabs import tab1_forecast, tab2_card, tab3_tax  # tabs 폴더 내부 파일들
import pandas as pd

load_dotenv()
st.set_page_config(page_title="AI 가결산 대시보드 Pro", layout="wide")

# --- 사이드바 ---
with st.sidebar:
    st.header("⚙️ 설정")
    env_api_key = os.getenv("GEMINI_API_KEY", "")
    api_key = st.text_input("Gemini API Key", value=env_api_key, type="password")
    
    st.markdown("---")
    st.header("📂 데이터 로드")
    file_pl_up = st.file_uploader("손익계산서", type="json")
    file_2024_up = st.file_uploader("2024 분개장", type="json")
    file_2025_up = st.file_uploader("2025 분개장", type="json")
    file_card_up = st.file_uploader("신용카드 내역", type="json")
    file_rec_up = st.file_uploader("신고서 데이터", type="json")
    
    # 데이터 로드 실행 (utils 함수 사용)
    # 주의: 로컬 파일명은 실제 파일명과 일치해야 합니다.
    json_pl = utils.load_local_or_uploaded(file_pl_up, "jsons/손익계산서_24년_25년.json")
    json_2024 = utils.load_local_or_uploaded(file_2024_up, "jsons/2024.json")
    json_2025 = utils.load_local_or_uploaded(file_2025_up, "jsons/2025.json")
    json_card = utils.load_local_or_uploaded(file_card_up, "jsons/신용카드_6.json") # 파일명 수정됨
    json_rec = utils.load_local_or_uploaded(file_rec_up, "jsons/rec_prd.json")
    
    if json_2025: st.success("✅ 데이터 로드 완료")
    else: st.error("❌ 2025년 데이터가 필요합니다.")

# --- 데이터 처리 (utils 함수 사용) ---
df_2024 = utils.preprocess_journal(json_2024)
df_2025 = utils.preprocess_journal(json_2025)

# 1. 전년도 학습
history_map = utils.build_history_map(df_2024)

revenue_ytd, expense_ytd = 0, 0
rev_24_total, exp_24_total = 0, 0

if json_pl:
    rev_24_total, exp_24_total = utils.parse_income_statement(json_pl)
if not df_2025.empty:
    revenue_ytd, expense_ytd = utils.calculate_financials(df_2025)

card_gap_amt = 0
missing_df = pd.DataFrame() # 빈 데이터프레임 초기화 (pandas 필요)
import pandas as pd # 여기서 import 하거나 맨 위에서 함

if not df_2025.empty and json_card:
    # history_map 전달
    card_gap_amt, missing_df = utils.analyze_card_gap(df_2025, json_card, history_map)

# --- 메인 화면 (탭 연결) ---
if not df_2025.empty:
    st.title("📊 AI 가결산 & 세무 예측 솔루션")
    
    tab1, tab2, tab3 = st.tabs(["📈 손익 예측", "💳 카드 누락 분석", "💰 세금 시뮬레이터"])
    
    with tab1:
        # Tab 1 렌더링 및 예측값 받아오기
        forecast_data = tab1_forecast.render(revenue_ytd, expense_ytd, rev_24_total, card_gap_amt)
        
    with tab2:
        # Tab 2 렌더링
        tab2_card.render(card_gap_amt, missing_df, api_key)
        
    with tab3:
        # Tab 3 렌더링 (Tab 1의 결과값 전달)
        # 고정 변수들 (타소득 등)은 여기서 전달
        tab3_tax.render(forecast_data, card_gap_amt, 7343097, 16581120, 2535610)

else:
    st.info("👈 데이터를 로드해주세요.")