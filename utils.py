import pandas as pd
import json
import os
import google.generativeai as genai
from collections import Counter

# --- 데이터 로드 ---
def load_json_file(uploaded_file):
    if uploaded_file is not None:
        try:
            return json.load(uploaded_file)
        except:
            return None
    return None

def load_local_or_uploaded(uploaded_file, default_path):
    if uploaded_file is not None:
        return load_json_file(uploaded_file)
    else:
        if os.path.exists(default_path):
            try:
                with open(default_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return None
    return None

# --- 데이터 전처리 ---
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

# --- 카드 분석 ---
def build_history_map(df_2024):
    if df_2024.empty or 'nm_trade' not in df_2024.columns: return {}
    history = {}
    grouped = df_2024.groupby('nm_trade')['nm_acctit'].apply(list)
    for merchant, accounts in grouped.items():
        if not merchant or merchant.strip() == "": continue
        most_common = Counter(accounts).most_common(1)[0][0]
        history[merchant.strip()] = most_common
    return history

def get_status_name(code):
    mapping = {1: "미추천", 2: "확정", 3: "확정가능", 5: "삭제전표", 6: "불공제"}
    return mapping.get(code, f"기타({code})")

def analyze_card_gap(df_journal, card_data, history_map):
    if df_journal.empty or not card_data: return 0, pd.DataFrame()
    
    # 데이터 구조 확인 (리스트인지 딕셔너리인지)
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
        
        if status_code == 2 and key not in journal_keys:
            merchant = str(row.get('nm_trade', '')).strip()
            
            # 업종 정보 (질문하신 내용 반영)
            biz_cond = str(row.get('bizcond', '')).strip()
            biz_cate = str(row.get('bizcate', '')).strip()
            industry = f"{biz_cond} / {biz_cate}" if biz_cond or biz_cate else ""
            
            # 비고란 로직 (전년도 > 추천 > 미분류)
            history_hint = history_map.get(merchant, "")
            acct_hint = str(row.get('nm_acctit_cha', '')).strip()
            
            remark_display = ""
            if history_hint:
                remark_display = f"💡전년도: {history_hint}"
            elif acct_hint:
                remark_display = f"추천: {acct_hint}"
            else:
                remark_display = "미분류"

            unmatched_items.append({
                "일자": row.get('da_sbook', ''),
                "거래처": merchant,
                "업종(업태/종목)": industry,
                "금액": row.get('mn_total', 0),
                "전표상태": get_status_name(status_code),
                "비고(AI힌트)": remark_display,
                "전년도이력": history_hint
            })
            total_gap += row.get('mn_total', 0)
            
    return total_gap, pd.DataFrame(unmatched_items)

# --- 세금 및 AI ---
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
        당신은 회계 전문가입니다. 아래 신용카드 사용 내역을 보고 적절한 '계정과목'을 추천해주세요.
        [데이터] {unknown_items}
        [형식] JSON 포맷으로만 답해주세요. 예: {{"거래처명": "추천계정과목"}}
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