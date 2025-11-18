import streamlit as st
import pandas as pd
import json
import google.generativeai as genai
import plotly.graph_objects as go
import os
from dotenv import load_dotenv
from collections import Counter

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
    if not data: return pd.DataFrame()
    df = pd.DataFrame(data)
    
    cols = ['mn_bungae1', 'mn_bungae2']
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
            
    if 'da_date' in df.columns:
        df['da_date'] = df['da_date'].astype(str)
        remark = df.get('nm_remark', pd.Series(['']*len(df)))
        gubun = df.get('nm_gubun_prn', pd.Series(['']*len(df)))
        mask = (df['da_date'].str.endswith('1231')) & (
            remark.str.contains('손익|결산|대체', na=False) | 
            gubun.str.contains('결산', na=False)
        )
        return df[~mask].copy()
    return df

def calculate_financials(df):
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
    rev_24 = 0
    exp_24 = 0
    if not pl_data: return 0, 0
    for item in pl_data:
        name = item.get('nm_acctit', '')
        val_24 = item.get('mn_btotal2', 0)
        if "매출액" in name and "매출원가" not in name:
             rev_24 = val_24
        elif "판매비와" in name or "판관비" in name:
             exp_24 += val_24
        elif "영업외비용" in name:
             exp_24 += val_24
    return rev_24, exp_24

# --- [핵심 로직] 전년도 패턴 학습 ---
def build_history_map(df_2024):
    """2024년 장부에서 거래처별 자주 쓴 계정과목 추출"""
    if df_2024.empty or 'nm_trade' not in df_2024.columns:
        return {}
    
    history = {}
    # 거래처별 계정과목 리스트 수집
    grouped = df_2024.groupby('nm_trade')['nm_acctit'].apply(list)
    
    for merchant, accounts in grouped.items():
        if not merchant or merchant.strip() == "": continue
        # 가장 많이 등장한 계정과목 찾기 (최빈값)
        most_common = Counter(accounts).most_common(1)[0][0]
        history[merchant.strip()] = most_common
        
    return history

def get_status_name(code):
    """전표상태 코드 매핑"""
    mapping = {
        1: "미추천",
        2: "확정",
        3: "확정가능",
        5: "삭제전표",
        6: "불공제"
    }
    return mapping.get(code, f"기타({code})")

def analyze_card_gap(df_journal, card_data, history_map):
    """카드 내역 분석 (업종, 상태, 전년도 이력 포함)"""
    if df_journal.empty or not card_data: return 0, pd.DataFrame()
    
    card_list = card_data if isinstance(card_data, list) else card_data.get('data', [])
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
        status_code = row.get('ty_jungstat', 0)
        status_name = get_status_name(status_code)
        
        # 상태값 필터링 없이 모든 미반영 내역을 보여주되, 합계는 '확정'만 포함하거나 사용자가 선택하게 할 수 있음
        # 여기서는 리스트에는 다 보여주고, gap 계산은 '확정'된 것만 수행
        is_missing = key not in journal_keys
        
        if is_missing:
            merchant = str(row.get('nm_trade', '')).strip()
            
            # 1. 업종 정보
            biz_cond = str(row.get('bizcond', '')).strip()
            biz_cate = str(row.get('bizcate', '')).strip()
            industry = f"{biz_cond} / {biz_cate}" if biz_cond or biz_cate else ""
            
            # 2. 비고 (우선순위: 전년도 이력 > 카드사 추천 > 미분류)
            history_hint = history_map.get(merchant, "")
            acct_hint = str(row.get('nm_acctit_cha', '')).strip()
            
            remark_display = ""
            if history_hint:
                remark_display = f"💡전년도: {history_hint}"
            elif acct_hint:
                remark_display = f"추천: {acct_hint}"
            else:
                remark_display = "미분류"

            item_data = {
                "일자": row.get('da_sbook', ''),
                "거래처": merchant,
                "업종(업태/종목)": industry,
                "금액": row.get('mn_total', 0),
                "전표상태": status_name,
                "비고(AI힌트)": remark_display,
                "전년도이력": history_hint  # AI에게 보낼 데이터용
            }
            unmatched_items.append(item_data)
            
            # 갭 금액 합산은 '확정(2)'이면서 '장부미반영'인 것만
            if status_code == 2:
                total_gap += row.get('mn_total', 0)
            
    return total_gap, pd.DataFrame(unmatched_items)

def calculate_tax(base):
    if base <= 0: return 0
    elif base <= 14000000: return base * 0.06
    elif base <= 50000000: return base * 0.15 - 1260000
    elif base <= 88000000: return base * 0.24 - 5760000
    elif base <= 150000000: return base * 0.35 - 15440000
    else: return base * 0.38 - 19940000

# --- [AI 함수] ---
def categorize_expenses_with_ai(api_key, unknown_items):
    if not api_key: return "API 키가 필요합니다."
    try:
        genai.configure(api_key=api_key)
        prompt = f"""
        당신은 전문 회계사입니다. 아래 신용카드 사용 내역을 보고 적절한 '계정과목'을 추천해주세요.
        
        [분석 지침]
        1. '전년도이력'이 있다면 그 계정과목을 최우선으로 추천하세요.
        2. 없다면 '업종'과 '거래처'를 보고 판단하세요. (예: 통신업 -> 통신비, 식당 -> 복리후생비/접대비)
        3. '전표상태'가 '삭제전표'나 '미추천'이라면 "불공제/사적비용 검토필요"라고 코멘트하세요.
        
        [입력 데이터]
        {unknown_items}
        
        [출력 형식]
        JSON 포맷으로만 답해주세요. 예: {{"거래처명": {{"추천계정": "계정과목", "이유": "간략설명"}}}}
        """
        try:
            model = genai.GenerativeModel('gemini-2.0-flash')
            response = model.generate_content(prompt)
        except:
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"⚠️ AI 호출 실패: {str(e)}"

# --- [3] 메인 UI ---
st.title("📊 AI 가결산 & 세무 예측 솔루션")

with st.sidebar:
    st.header("⚙️ 설정")
    env_api_key = os.getenv("GEMINI_API_KEY", "")
    api_key = st.text_input("Gemini API Key", value=env_api_key, type="password")
    st.markdown("---")
    st.header("📂 데이터 로드")
    
    file_pl_up = st.file_uploader("손익계산서 (24-25년)", type="json")
    file_2024_up = st.file_uploader("2024년 분개장 (전년도 학습용)", type="json") # 추가됨
    file_2025_up = st.file_uploader("2025년 분개장", type="json")
    file_card_up = st.file_uploader("신용카드 내역", type="json")
    file_rec_up = st.file_uploader("신고서 데이터 (rec_prd)", type="json")
    
    # 자동 로드
    json_pl = load_local_or_uploaded(file_pl_up, "jsons/손익계산서_24년_25년.json")
    json_2024 = load_local_or_uploaded(file_2024_up, "jsons/2024.json")
    json_2025 = load_local_or_uploaded(file_2025_up, "jsons/2025.json")
    json_card = load_local_or_uploaded(file_card_up, "jsons/신용카드_6.json")
    json_rec = load_local_or_uploaded(file_rec_up, "jsons/rec_prd.json")
    
    if json_pl: st.success("✅ 손익계산서 로드됨")
    if json_2024: st.success("✅ 2024년 분개장 로드됨 (AI 학습 완료)")
    if json_2025: st.success(f"✅ 2025년 분개장 로드됨")
    if json_card: st.success("✅ 카드 데이터 로드됨")
    if json_rec: st.success("✅ 신고서 데이터 로드됨")

# 데이터 처리
df_2024 = preprocess_journal(json_2024)
df_2025 = preprocess_journal(json_2025)

# 1. 전년도 학습 (History Map 생성)
history_map = build_history_map(df_2024)

revenue_ytd = 0
expense_ytd = 0
rev_24_total = 0
exp_24_total = 0

if json_pl:
    rev_24_total, exp_24_total = parse_income_statement(json_pl)

if not df_2025.empty:
    revenue_ytd, expense_ytd = calculate_financials(df_2025)

card_gap_amt = 0
missing_df = pd.DataFrame()

# 카드 분석 시 history_map 전달
if not df_2025.empty and json_card:
    card_gap_amt, missing_df = analyze_card_gap(df_2025, json_card, history_map)

# 메인 로직
if not df_2025.empty:
    tab1, tab2, tab3 = st.tabs(["📈 손익 예측", "💳 카드 누락 분석", "💰 세금 시뮬레이터"])
    
    # [Tab 1] 손익 예측
    with tab1:
        st.subheader("2025년 연간 손익 추정 (Landing Forecast)")
        months_passed = 9
        rev_proj_avg = revenue_ytd / months_passed * 12
        if rev_24_total > 0:
            rev_24_ytd_approx = rev_24_total / 12 * months_passed
            growth_rate = revenue_ytd / rev_24_ytd_approx
            rev_proj_trend = rev_24_total * growth_rate
        else:
            rev_proj_trend = rev_proj_avg
        final_rev_baseline = max(rev_proj_avg, rev_proj_trend)
        proj_expense_simple = expense_ytd / months_passed * 12
        
        col1, col2, col3 = st.columns(3)
        col1.metric("2024년 확정 매출", f"{rev_24_total:,.0f} 원")
        col2.metric("2025년 예상 매출", f"{final_rev_baseline:,.0f} 원")
        col3.metric("2025년 장부상 비용", f"{proj_expense_simple:,.0f} 원")
        st.info(f"💡 2024년 확정 매출({rev_24_total:,.0f}원) 대비 2025년 매출은 **{((final_rev_baseline/rev_24_total)-1)*100:.1f}%** 변동될 것으로 예측됩니다.")

    # [Tab 2] 카드 누락 분석
    with tab2:
        st.subheader("신용카드 미처리 내역 (Gap Analysis)")
        c1, c2 = st.columns([3, 1])
        with c1:
            st.error(f"🚨 **총 누락 의심 금액 (확정전표 기준): {card_gap_amt:,.0f} 원**")
            
            if not missing_df.empty:
                # 상태값 필터링 옵션
                status_filter = st.multiselect("전표 상태 필터", 
                                             options=missing_df['전표상태'].unique(),
                                             default=['확정', '확정가능'])
                
                filtered_df = missing_df[missing_df['전표상태'].isin(status_filter)]
                
                st.dataframe(
                    filtered_df.sort_values('금액', ascending=False).head(200), 
                    width=1000,
                    column_config={
                        "금액": st.column_config.NumberColumn(format="%d 원"),
                        "비고(AI힌트)": st.column_config.TextColumn(help="전년도 장부 이력 또는 카드사 추천 계정"),
                        "업종(업태/종목)": st.column_config.TextColumn(width="medium")
                    }
                )
            else:
                st.write("누락된 내역이 없거나 데이터가 매칭되었습니다.")
                
        with c2:
            st.markdown("#### 🤖 AI 정밀 분석")
            st.info("전년도 처리 이력과 업종 정보를 기반으로 분석합니다.")
            if st.button("미분류 내역 AI 분석"):
                if api_key:
                    # AI에게 보낼 때 전년도 이력도 같이 보냄
                    cols_to_ai = ['거래처', '업종(업태/종목)', '금액', '전표상태', '전년도이력']
                    sample_data = filtered_df[cols_to_ai].head(10).to_dict(orient='records')
                    
                    with st.spinner("Gemini 2.0 Flash가 2024년 장부와 대조 중..."):
                        result = categorize_expenses_with_ai(api_key, str(sample_data))
                        st.success("분석 완료!")
                        st.code(result, language='json')
                else:
                    st.error("API 키가 없습니다.")

    # [Tab 3] 세금 시뮬레이터 (업그레이드 버전)
    with tab3:
        st.subheader("📝 2025년 귀속 종합소득세 시뮬레이션")
        
        # 1. 시나리오 선택
        scenario = st.select_slider(
            "경영 시나리오 선택",
            options=["S1(극단적 보수)", "S2(보수적)", "S3(합리적 보수)", "S4(전략적)"],
            value="S3(합리적 보수)"
        )
        
        # 변수 설정 (고정값)
        other_income = 7343097 
        deduction = 16581120
        disallowed = 2535610
        
        # 시나리오 로직
        if scenario == "S1(극단적 보수)":
            final_rev = final_rev_baseline
            final_exp = proj_expense_simple
            gap_applied = 0
            desc = "현재 장부상 비용만 인정 (카드 누락분 0원)"
        elif scenario == "S2(보수적)":
            final_rev = final_rev_baseline
            gap_applied = card_gap_amt * 0.5
            final_exp = proj_expense_simple + gap_applied
            desc = "카드 누락분의 50%만 반영"
        elif scenario == "S3(합리적 보수)":
            final_rev = final_rev_baseline
            # 연간 환산 누락분 (단순 합산이 아니라 연간 비율로)
            annual_card_gap = card_gap_amt / months_passed * 12
            gap_applied = annual_card_gap
            final_exp = proj_expense_simple + gap_applied
            desc = "카드 누락분과 미래 비용을 모두 반영한 현실적 수치 ⭐"
        else: # S4 전략적
            annual_card_gap = card_gap_amt / months_passed * 12
            gap_applied = annual_card_gap + 4000000
            final_rev = final_rev_baseline * 0.95 
            final_exp = proj_expense_simple + gap_applied
            desc = "매출 감소 + 연말 전략적 지출(+400만)"

        # 세금 계산
        tax_base = final_rev + other_income - final_exp - deduction + disallowed
        if tax_base < 0: tax_base = 0
        calc_tax_amt = calculate_tax(tax_base)
        total_tax = calc_tax_amt * 1.1 
        
        # 2. 결과 표시 (메인 지표)
        col_res1, col_res2 = st.columns([1, 2])
        
        with col_res1:
            st.metric("예상 납부 세액 (지방세 포함)", f"{total_tax:,.0f} 원")
            st.caption(f"적용 세율 구간: {int(calc_tax_amt/tax_base*100 if tax_base else 0)}% (누진공제 반영 전)")
            
            # 3. [NEW] 산출 근거 상세 보기 (추론 과정 설명)
            with st.expander("🔍 세금은 어떻게 계산됐나요? (상세 보기)"):
                st.markdown(f"""
                **1. 총 수입금액: {final_rev + other_income:,.0f} 원**
                - 사업 매출: {final_rev:,.0f} 원 (평균법 적용)
                - 타소득 합산: {other_income:,.0f} 원 (전년도 신고 기준)
                
                **2. 필요 경비: {final_exp:,.0f} 원**
                - 장부상 비용: {proj_expense_simple:,.0f} 원
                - **(+) 누락/보정분: {gap_applied:,.0f} 원** *(카드 누락 및 미래 발생분 포함)*
                
                **3. 세무 조정: {disallowed - deduction:,.0f} 원**
                - (+) 비용 부인액: {disallowed:,.0f} 원 (차량 등)
                - (-) 소득 공제: {deduction:,.0f} 원 (노란우산 등)
                
                ---
                **(=) 과세표준: {tax_base:,.0f} 원**
                """)

        with col_res2:
            fig = go.Figure(go.Waterfall(
                name = "Tax Flow", orientation = "v",
                measure = ["relative", "relative", "relative", "relative", "total", "total"],
                x = ["총매출", "타소득/조정", "비용(예상)", "소득공제", "과세표준", "납부세액"],
                y = [final_rev, other_income+disallowed, -final_exp, -deduction, tax_base, total_tax],
                connector = {"line":{"color":"rgb(63, 63, 63)"}},
                decreasing = {"marker":{"color":"green"}},
                increasing = {"marker":{"color":"red"}},
                totals = {"marker":{"color":"blue"}}
            ))
            st.plotly_chart(fig, use_container_width=True)

        # 4. [NEW] AI 보고서 생성 버튼
        st.divider()
        if st.button("📄 AI 경영 컨설팅 보고서 생성하기"):
            if api_key:
                with st.spinner("Gemini가 재무/세무 데이터를 분석하여 보고서를 작성 중입니다..."):
                    # 프롬프트 구성
                    report_prompt = f"""
                    당신은 20년 경력의 재무/세무 전문 컨설턴트입니다. 
                    아래 시뮬레이션 데이터를 바탕으로 경영자에게 보고할 '2025년 가결산 및 절세 전략 보고서'를 작성해주세요.
                    
                    [시뮬레이션 데이터]
                    - 시나리오: {scenario} ({desc})
                    - 예상 연매출: {final_rev:,.0f}원
                    - 예상 총비용: {final_exp:,.0f}원 (누락 보정분 {gap_applied:,.0f}원 포함)
                    - 예상 과세표준: {tax_base:,.0f}원
                    - 예상 납부세액: {total_tax:,.0f}원
                    - 주요 이슈: 카드 누락분 반영 여부가 세금에 큰 영향을 미침.
                    
                    [보고서 목차 및 요구사항]
                    1. **경영 진단 요약**: 현재 예상되는 손익과 세금 상황을 직관적으로 요약 (이모지 사용).
                    2. **시나리오 분석**: 선택된 시나리오({scenario})가 왜 합리적인지, 혹은 위험한지 설명.
                    3. **절세 액션 플랜**: 남은 기간(11~12월) 동안 실행해야 할 구체적인 행동 3가지 (카드 처리, 소모품 구매 등).
                    4. **전문가 제언**: 자금 흐름 관점에서 주의할 점 한 마디.
                    
                    어조는 정중하고 전문적이면서도, 경영자가 바로 실행할 수 있도록 명확하게 작성해주세요.
                    """
                    
                    # AI 호출
                    try:
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel('gemini-2.0-flash')
                        report_text = model.generate_content(report_prompt).text
                        
                        # 보고서 출력
                        st.markdown("### 📑 2025년 가결산 및 절세 전략 보고서")
                        st.markdown(report_text)
                        
                        # 다운로드 버튼 (텍스트 파일)
                        st.download_button(
                            label="보고서 다운로드 (TXT)",
                            data=report_text,
                            file_name="2025_Tax_Report.txt",
                            mime="text/plain"
                        )
                    except Exception as e:
                        st.error(f"보고서 생성 실패: {e}")
            else:
                st.error("API 키가 필요합니다.")