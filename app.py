import streamlit as st
import pandas as pd
import json
import google.generativeai as genai
import plotly.graph_objects as go
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# --- [1] 설정 및 유틸리티 ---
st.set_page_config(page_title="AI 가결산 대시보드 Pro", layout="wide")

@st.cache_data
def load_json_file(uploaded_file):
    if uploaded_file is not None:
        try:
            return json.load(uploaded_file)
        except Exception as e:
            st.error(f"파일 로드 오류: {e}")
            return None
    return None

def load_local_or_uploaded(uploaded_file, default_path):
    """업로드된 파일 우선, 없으면 로컬 경로 파일 로드"""
    if uploaded_file is not None:
        try:
            return json.load(uploaded_file)
        except Exception as e:
            st.error(f"업로드 파일 로드 오류: {e}")
            return None
    else:
        if os.path.exists(default_path):
            try:
                with open(default_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return None
    return None

def preprocess_journal(data):
    """분개장 데이터를 DataFrame으로 변환 및 전처리"""
    if not data: return pd.DataFrame()
    df = pd.DataFrame(data)
    
    cols = ['mn_bungae1', 'mn_bungae2']
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
            
    if 'da_date' in df.columns:
        df['da_date'] = df['da_date'].astype(str)
        
        # 결산 분개 제거 (12/31 & 손익/결산 키워드)
        remark = df.get('nm_remark', pd.Series(['']*len(df)))
        gubun = df.get('nm_gubun_prn', pd.Series(['']*len(df)))
        mask = (df['da_date'].str.endswith('1231')) & (
            remark.str.contains('손익|결산|대체', na=False) | 
            gubun.str.contains('결산', na=False)
        )
        return df[~mask].copy()
    return df

def calculate_financials(df):
    """매출(4)과 비용(5,8,9) 집계"""
    if df.empty: return 0, 0
    
    if 'cd_acctit' in df.columns:
        df['cd_acctit'] = df['cd_acctit'].astype(str)
        rev_df = df[df['cd_acctit'].str.startswith('4', na=False)]
        revenue = (rev_df['mn_bungae2'] - rev_df['mn_bungae1']).sum()
        
        exp_df = df[df['cd_acctit'].str.startswith(('5','8','9'), na=False)]
        expense = (exp_df['mn_bungae1'] - exp_df['mn_bungae2']).sum()
        
        return revenue, expense
    return 0, 0

def parse_income_statement(pl_data):
    """손익계산서 JSON에서 2024년 확정 매출/비용 추출"""
    # 구조에 따라 파싱 로직이 달라질 수 있음 (예시: 리스트 형태 가정)
    # mn_total1: 당기(2025), mn_btotal1: 전기(2024) 라고 가정하거나
    # mn_total1: 2024, mn_btotal1: 2023 일 수도 있음.
    # 제공해주신 파일 구조([{"nm_acctit": "Ⅰ. 매출액", "mn_total1": 123812716 (2025), "mn_btotal1": 168399913 (2024)}...]) 기준
    
    rev_24 = 0
    exp_24 = 0
    
    if not pl_data: return 0, 0
    
    for item in pl_data:
        name = item.get('nm_acctit', '')
        # 2024년 데이터는 보통 '전기(Prior)' 컬럼인 mn_btotal1 또는 mn_btotal2 등에 있음
        # 2025년 9월 기준 손익계산서라면, mn_total1이 2025년, mn_btotal1이 2024년 전체일 가능성 높음
        val_24 = item.get('mn_btotal2', 0) # 2024년 (전기)
        
        if "매출액" in name and "매출원가" not in name:
             rev_24 = val_24
        elif "판매비와" in name or "판관비" in name: # 판매비와 관리비
             exp_24 += val_24
        elif "영업외비용" in name:
             exp_24 += val_24
        # 영업외수익 등은 별도 처리 필요하나 여기선 단순화
        
    return rev_24, exp_24

def analyze_card_gap(df_journal, card_data):
    if df_journal.empty or not card_data: return 0, pd.DataFrame()
    card_list = card_data.get('data', [])
    if not card_list: return 0, pd.DataFrame()
    
    df_card = pd.DataFrame(card_list)
    if 'da_date' in df_journal.columns and 'mn_bungae1' in df_journal.columns:
        journal_keys = set(df_journal['da_date'] + "_" + df_journal['mn_bungae1'].astype(int).astype(str))
    else:
        journal_keys = set()
    
    unmatched_items = []
    total_gap = 0
    for _, row in df_card.iterrows():
        key = str(row.get('da_sbook','')) + "_" + str(int(row.get('mn_total', 0)))
        status = row.get('ty_jungstat', 0)
        if status == 2 and key not in journal_keys:
            unmatched_items.append({
                "거래처": row.get('nm_trade', ''),
                "금액": row.get('mn_total', 0),
                "일자": row.get('da_sbook', ''),
                "비고": "장부 미반영"
            })
            total_gap += row.get('mn_total', 0)
    return total_gap, pd.DataFrame(unmatched_items)

def calculate_tax(base):
    if base <= 0: return 0
    elif base <= 14000000: return base * 0.06
    elif base <= 50000000: return base * 0.15 - 1260000
    elif base <= 88000000: return base * 0.24 - 5760000
    elif base <= 150000000: return base * 0.35 - 15440000
    else: return base * 0.38 - 19940000

def categorize_expenses_with_ai(api_key, unknown_items):
    if not api_key: return "API 키가 필요합니다."
    try:
        genai.configure(api_key=api_key)
        
        prompt = f"""
        당신은 전문 회계사입니다. 다음 카드 내역의 '거래처'와 '금액'을 보고 적절한 계정과목을 추론해주세요.
        [데이터] {unknown_items}
        [형식] JSON 포맷으로만 답해주세요. 예: {{"거래처명": "계정과목"}}
        """
        
        # [수정됨] 1.5-flash 대신 대표님 계정에 있는 '2.0-flash' 사용
        try:
            # 1순위: Gemini 2.0 Flash (최신/고성능)
            model = genai.GenerativeModel('gemini-2.0-flash')
            response = model.generate_content(prompt)
        except:
            # 2순위: 혹시 안 되면 2.5 Flash 시도
            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content(prompt)
            
        return response.text
        
    except Exception as e:
        return f"⚠️ AI 호출 실패: {str(e)}"

# --- [3] 메인 대시보드 UI ---
st.title("📊 AI 가결산 & 세무 예측 솔루션")

with st.sidebar:
    st.header("⚙️ 설정")
    env_api_key = os.getenv("GEMINI_API_KEY", "")
    api_key = st.text_input("Gemini API Key", value=env_api_key, type="password", help=".env 파일에 키가 있으면 자동 입력됩니다.")
    
    st.markdown("---")
    st.header("📂 데이터 로드")
    
    file_pl_up = st.file_uploader("손익계산서 (24-25년)", type="json")
    file_2025_up = st.file_uploader("2025년 분개장", type="json")
    file_card_up = st.file_uploader("신용카드 내역", type="json")
    file_rec_up = st.file_uploader("신고서 데이터 (rec_prd)", type="json")
    
    # 자동 로드 (파일명 수정됨)
    json_pl = load_local_or_uploaded(file_pl_up, "jsons/손익계산서_24년_25년.json")
    json_2025 = load_local_or_uploaded(file_2025_up, "jsons/2025.json")
    json_card = load_local_or_uploaded(file_card_up, "jsons/신용카드_6.json")
    json_rec = load_local_or_uploaded(file_rec_up, "jsons/rec_prd.json")
    
    if json_pl: st.success("✅ 손익계산서 로드됨")
    if json_2025: st.success(f"✅ 2025년 분개장 로드됨 ({len(json_2025)}건)")
    if json_card: st.success("✅ 카드 데이터 로드됨")
    if json_rec: st.success("✅ 신고서 데이터 로드됨")

# --- 데이터 처리 및 공통 변수 ---
df_2025 = preprocess_journal(json_2025)
revenue_ytd = 0
expense_ytd = 0
rev_24_total = 0
exp_24_total = 0

# 1. 손익계산서에서 2024년 확정 실적 가져오기 (우선순위 1)
if json_pl:
    rev_24_total, exp_24_total = parse_income_statement(json_pl)

# 2. 2025년 실적 집계
if not df_2025.empty:
    revenue_ytd, expense_ytd = calculate_financials(df_2025)

# 3. 카드 누락분 분석
card_gap_amt = 0
missing_df = pd.DataFrame()
if not df_2025.empty and json_card:
    card_gap_amt, missing_df = analyze_card_gap(df_2025, json_card)

# 메인 로직
if not df_2025.empty:
    # 탭 구성
    tab1, tab2, tab3 = st.tabs(["📈 손익 예측", "💳 카드 누락 분석", "💰 세금 시뮬레이터"])
    
    # [Tab 1] 손익 예측
    with tab1:
        st.subheader("2025년 연간 손익 추정 (Landing Forecast)")
        
        months_passed = 9
        
        # A. 평균법 (25년 실적 연환산)
        rev_proj_avg = revenue_ytd / months_passed * 12
        
        # B. 추세법 (24년 손익계산서 확정치 기준 성장률)
        if rev_24_total > 0:
            rev_24_ytd_approx = rev_24_total / 12 * months_passed
            growth_rate = revenue_ytd / rev_24_ytd_approx
            rev_proj_trend = rev_24_total * growth_rate
        else:
            rev_proj_trend = rev_proj_avg
            
        # 보수적 매출 (Max)
        final_rev_baseline = max(rev_proj_avg, rev_proj_trend)
        
        # 비용 예측
        proj_expense_simple = expense_ytd / months_passed * 12
        
        col1, col2, col3 = st.columns(3)
        col1.metric("2024년 확정 매출", f"{rev_24_total:,.0f} 원", help="손익계산서 기준")
        col2.metric("2025년 예상 매출", f"{final_rev_baseline:,.0f} 원")
        col3.metric("2025년 장부상 비용", f"{proj_expense_simple:,.0f} 원")
        
        st.info(f"💡 2024년 확정 매출({rev_24_total:,.0f}원) 대비 2025년 매출은 **{((final_rev_baseline/rev_24_total)-1)*100:.1f}%** 변동될 것으로 예측됩니다.")

    # [Tab 2] 카드 누락 분석
    with tab2:
        st.subheader("신용카드 미처리 내역 (Gap Analysis)")
        c1, c2 = st.columns([3, 1])
        with c1:
            st.error(f"🚨 **총 누락 의심 금액: {card_gap_amt:,.0f} 원**")
            if not missing_df.empty:
                st.dataframe(missing_df.sort_values('금액', ascending=False).head(100), width=700)
            else:
                st.write("누락된 내역이 없거나 데이터가 매칭되었습니다.")
        with c2:
            st.markdown("#### 🤖 AI 계정 분류")
            if st.button("미분류 내역 AI 분석"):
                if api_key:
                    sample_data = missing_df.head(5).to_dict(orient='records') if not missing_df.empty else "샘플 데이터 없음"
                    with st.spinner("Gemini가 분석 중..."):
                        result = categorize_expenses_with_ai(api_key, str(sample_data))
                        st.success("분류 완료!")
                        st.code(result)
                else:
                    st.error("API 키가 없습니다.")

    # [Tab 3] 세금 시뮬레이터
    with tab3:
        st.subheader("📝 2025년 귀속 종합소득세 시뮬레이션")
        
        scenario = st.select_slider(
            "시나리오 선택",
            options=["S1(극단적 보수)", "S2(보수적)", "S3(합리적 보수)", "S4(전략적)"],
            value="S3(합리적 보수)"
        )
        
        other_income = 7343097
        deduction = 16581120
        disallowed = 2535610
        
        if scenario == "S1(극단적 보수)":
            final_rev_tax = final_rev_baseline
            final_exp_tax = proj_expense_simple
            desc = "현재 장부상 비용만 인정 (카드 누락분 0원)"
        elif scenario == "S2(보수적)":
            final_rev_tax = final_rev_baseline
            final_exp_tax = proj_expense_simple + (card_gap_amt * 0.5)
            desc = "카드 누락분의 50%만 반영"
        elif scenario == "S3(합리적 보수)":
            final_rev_tax = final_rev_baseline
            annual_card_gap = card_gap_amt / months_passed * 12
            final_exp_tax = proj_expense_simple + annual_card_gap
            desc = "카드 누락분과 미래 비용을 모두 반영한 현실적 수치 ⭐"
        else: # S4
            annual_card_gap = card_gap_amt / months_passed * 12
            final_rev_tax = final_rev_baseline * 0.95
            final_exp_tax = proj_expense_simple + annual_card_gap + 4000000
            desc = "매출 감소 + 연말 전략적 지출(+400만)"

        tax_base = final_rev_tax + other_income - final_exp_tax - deduction + disallowed
        if tax_base < 0: tax_base = 0
        calc_tax = calculate_tax(tax_base)
        total_tax = calc_tax * 1.1
        
        col_res1, col_res2 = st.columns(2)
        with col_res1:
            st.metric("예상 납부 세액 (지방세 포함)", f"{total_tax:,.0f} 원")
            st.caption(f"과세표준: {tax_base:,.0f} 원")
            st.info(f"**시나리오:** {desc}")
            
        with col_res2:
            fig = go.Figure(go.Waterfall(
                name = "Tax", orientation = "v",
                measure = ["relative", "relative", "relative", "relative", "total", "total"],
                x = ["총매출", "타소득/조정", "비용(예상)", "소득공제", "과세표준", "납부세액"],
                y = [final_rev_tax, other_income+disallowed, -final_exp_tax, -deduction, tax_base, total_tax],
                connector = {"line":{"color":"rgb(63, 63, 63)"}},
                decreasing = {"marker":{"color":"green"}},
                increasing = {"marker":{"color":"red"}},
                totals = {"marker":{"color":"blue"}}
            ))
            st.plotly_chart(fig, use_container_width=True)

else:
    st.info("👈 데이터를 로드해주세요. (jsons 폴더에 파일이 있으면 자동 로드됩니다)")