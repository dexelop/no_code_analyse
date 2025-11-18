import streamlit as st

def render(revenue_ytd, expense_ytd, rev_24_total, card_gap_amt):
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
    method_used = "평균법" if final_rev_baseline == rev_proj_avg else "추세법"
    
    # 비용 분석 (3단 분리)
    exp_booked = expense_ytd
    exp_missing = card_gap_amt
    
    # 미래 비용 예측 (현재 월평균 + 누락분 반영된 월평균)
    monthly_real_burn = (expense_ytd + card_gap_amt) / months_passed
    exp_future = monthly_real_burn * (12 - months_passed)
    
    final_exp_projected = exp_booked + exp_missing + exp_future
    final_profit = final_rev_baseline - final_exp_projected
    
    # UI 출력
    col1, col2, col3 = st.columns(3)
    col1.metric("예상 연매출 (Max)", f"{final_rev_baseline:,.0f} 원", f"{method_used}")
    col2.metric("예상 연간 총비용", f"{final_exp_projected:,.0f} 원", "누락+미래 포함")
    col3.metric("예상 영업이익", f"{final_profit:,.0f} 원")
    
    st.divider()
    
    # 상세 리포트
    st.markdown("### 🧐 AI 경영 분석 리포트")
    c1, c2 = st.columns(2)
    with c1:
        st.info("📊 **매출 예측: 보수적 접근**")
        st.markdown(f"- 1~9월 실적 기반 연환산(**평균법**)과 전년 대비 성장률(**추세법**) 중 더 높은 **{final_rev_baseline:,.0f}원**을 채택했습니다.")
    with c2:
        st.warning("💸 **비용 구조: 숨겨진 비용 발굴**")
        st.markdown(f"""
        - **기록됨(Booked):** {exp_booked:,.0f} 원
        - **누락됨(Missing):** {exp_missing:,.0f} 원 🚨 (카드 미처리)
        - **미래(Future):** {exp_future:,.0f} 원 (남은 3개월 예상)
        """)
    
    st.success(f"💡 **최종 진단:** 장부상 이익은 과대평가 상태입니다. 누락분과 미래 비용을 모두 반영한 **{final_profit:,.0f}원**이 실제 예상 이익입니다.")

    # 계산된 값 반환 (Tab 3 등에서 쓰기 위해)
    return {
        "final_rev_baseline": final_rev_baseline,
        "proj_expense_simple": expense_ytd / months_passed * 12, # 단순 연환산 (누락 미반영)
        "months_passed": months_passed
    }