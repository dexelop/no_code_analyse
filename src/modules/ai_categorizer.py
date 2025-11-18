"""
AI 계정 분류 모듈 (회사 패턴 학습 기반)
"""
import pandas as pd
import re
from typing import Dict, List, Tuple
import google.generativeai as genai


def analyze_company_patterns(df_journal: pd.DataFrame) -> Dict[str, str]:
    """
    회사의 과거 분류 패턴을 분석합니다.

    Args:
        df_journal: 분개장 DataFrame

    Returns:
        Dict[거래처명, 주로 사용한 계정과목]
    """
    if df_journal.empty or 'nm_trade' not in df_journal.columns or 'nm_acctit' not in df_journal.columns:
        return {}

    # 거래처별 가장 많이 사용한 계정과목 추출
    patterns = {}

    for trade_name in df_journal['nm_trade'].dropna().unique():
        if not trade_name or trade_name.strip() == "":
            continue

        # 해당 거래처의 모든 거래 필터링
        trade_rows = df_journal[df_journal['nm_trade'] == trade_name]

        # 가장 많이 사용한 계정과목
        if not trade_rows.empty and 'nm_acctit' in trade_rows.columns:
            most_common = trade_rows['nm_acctit'].mode()
            if len(most_common) > 0:
                patterns[trade_name] = most_common[0]

    return patterns


def find_similar_trade_patterns(df_journal: pd.DataFrame, keyword: str) -> Dict[str, List[str]]:
    """
    키워드를 포함하는 거래처들의 계정과목 패턴을 찾습니다.

    Args:
        df_journal: 분개장 DataFrame
        keyword: 검색 키워드 (예: "카페", "편의점", "식당")

    Returns:
        Dict[계정과목, [거래처명 리스트]]
    """
    if df_journal.empty or 'nm_trade' not in df_journal.columns or 'nm_acctit' not in df_journal.columns:
        return {}

    # 키워드를 포함하는 거래처 필터링
    pattern = re.compile(keyword, re.IGNORECASE)
    matching_rows = df_journal[df_journal['nm_trade'].str.contains(pattern, na=False)]

    if matching_rows.empty:
        return {}

    # 계정과목별로 거래처 그룹화
    result = {}
    for acctit in matching_rows['nm_acctit'].dropna().unique():
        trades = matching_rows[matching_rows['nm_acctit'] == acctit]['nm_trade'].unique().tolist()
        result[acctit] = trades

    return result


def get_category_examples(df_journal: pd.DataFrame, keyword_pattern: str, top_n: int = 3) -> str:
    """
    키워드 패턴에 맞는 거래처들의 계정 분류 예시를 반환합니다.

    Args:
        df_journal: 분개장 DataFrame
        keyword_pattern: 정규식 패턴 (예: "카페|커피|스타벅스")
        top_n: 상위 N개 계정과목만 반환

    Returns:
        예시 문자열
    """
    similar = find_similar_trade_patterns(df_journal, keyword_pattern)

    if not similar:
        return "관련 패턴 없음"

    # 빈도순으로 정렬
    sorted_patterns = sorted(similar.items(), key=lambda x: len(x[1]), reverse=True)[:top_n]

    examples = []
    for acctit, trades in sorted_patterns:
        examples.append(f"{acctit} ({len(trades)}건): {', '.join(trades[:3])}")

    return "\n".join(examples)


def get_top_accounts(df_journal: pd.DataFrame, top_n: int = 10) -> List[str]:
    """
    회사에서 가장 많이 사용하는 계정과목 TOP N을 반환합니다.

    Args:
        df_journal: 분개장 DataFrame
        top_n: 상위 N개

    Returns:
        계정과목 리스트
    """
    if df_journal.empty or 'nm_acctit' not in df_journal.columns:
        return []

    top_accounts = df_journal['nm_acctit'].value_counts().head(top_n).index.tolist()
    return top_accounts


def calculate_confidence(df_journal: pd.DataFrame, trade_name: str, suggested_account: str) -> Tuple[float, str]:
    """
    제안된 계정과목의 신뢰도를 계산합니다.

    Args:
        df_journal: 분개장 DataFrame
        trade_name: 거래처명
        suggested_account: 제안된 계정과목

    Returns:
        (신뢰도 %, 근거 설명)
    """
    if df_journal.empty:
        return 0.0, "데이터 없음"

    # 1. 정확히 같은 거래처가 있는 경우
    exact_matches = df_journal[df_journal['nm_trade'] == trade_name]
    if not exact_matches.empty:
        total = len(exact_matches)
        matching = len(exact_matches[exact_matches['nm_acctit'] == suggested_account])
        confidence = (matching / total) * 100
        return confidence, f"동일 거래처 {total}건 중 {matching}건이 해당 계정 사용"

    # 2. 유사한 거래처 패턴으로 신뢰도 계산
    # 거래처명에서 키워드 추출 (간단한 방법: 첫 단어)
    keywords = trade_name.split()
    if keywords:
        keyword = keywords[0]
        similar_trades = df_journal[df_journal['nm_trade'].str.contains(keyword, na=False)]

        if not similar_trades.empty:
            total = len(similar_trades)
            matching = len(similar_trades[similar_trades['nm_acctit'] == suggested_account])
            confidence = (matching / total) * 100
            return confidence, f"유사 거래처('{keyword}' 포함) {total}건 중 {matching}건이 해당 계정 사용"

    return 50.0, "과거 패턴 없음 (AI 일반 지식 기반)"


def categorize_with_company_context(
    api_key: str,
    unknown_items: List[Dict],
    df_journal: pd.DataFrame
) -> str:
    """
    회사의 과거 패턴을 학습하여 AI로 계정과목을 분류합니다.

    Args:
        api_key: Gemini API Key
        unknown_items: 미분류 항목 리스트 [{"거래처": "...", "금액": ...}, ...]
        df_journal: 분개장 DataFrame (과거 패턴 학습용)

    Returns:
        AI의 분류 결과 (JSON 형식 문자열)
    """
    if not api_key:
        return "API 키가 필요합니다."

    if not unknown_items:
        return "분류할 항목이 없습니다."

    try:
        # 1. 회사 내부 패턴 분석
        company_patterns = analyze_company_patterns(df_journal)

        # 샘플링 (너무 많으면 토큰 낭비)
        sample_patterns = dict(list(company_patterns.items())[:20])

        # 2. 카테고리별 예시 패턴
        cafe_pattern = get_category_examples(df_journal, "카페|커피|스타벅스|투썸|이디야", top_n=2)
        mart_pattern = get_category_examples(df_journal, "GS|CU|세븐|편의점|마트|쿠팡", top_n=2)
        food_pattern = get_category_examples(df_journal, "식당|음식점|배달|요기요", top_n=2)

        # 3. 자주 사용하는 계정과목 TOP 10
        top_accounts = get_top_accounts(df_journal, top_n=10)

        # 4. AI 프롬프트 구성
        genai.configure(api_key=api_key)

        prompt = f"""
당신은 이 회사의 회계 담당자입니다. 과거 분개 패턴을 학습하여 신규 거래를 분류해주세요.

[이 회사의 과거 거래처별 계정 분류 패턴] (샘플 20건)
{sample_patterns}

[카테고리별 분류 사례]
<카페/커피>
{cafe_pattern}

<편의점/마트>
{mart_pattern}

<식당/음식>
{food_pattern}

[이 회사에서 자주 사용하는 계정과목 TOP 10]
{', '.join(top_accounts)}

위 패턴을 참고하여 다음 미분류 항목을 분류해주세요:
{unknown_items}

중요:
1. 과거 패턴에 정확히 일치하는 거래처가 있으면 그 계정을 우선 사용하세요.
2. 유사한 거래처 패턴을 참고하세요 (예: 카페류는 대부분 접대비).
3. 가능한 한 회사가 자주 사용하는 계정과목 범위 내에서 선택하세요.
4. 반드시 JSON 형식으로만 답변하세요.

[출력 형식]
{{
  "거래처명": {{
    "계정과목": "추천 계정과목",
    "신뢰도": "높음/중간/낮음",
    "근거": "선택 근거"
  }}
}}
"""

        # 5. AI 모델 호출
        try:
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            response = model.generate_content(prompt)
        except:
            try:
                model = genai.GenerativeModel('gemini-1.5-flash')
                response = model.generate_content(prompt)
            except:
                model = genai.GenerativeModel('gemini-pro')
                response = model.generate_content(prompt)

        return response.text

    except Exception as e:
        return f"⚠️ AI 호출 실패: {str(e)}"
