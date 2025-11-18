import streamlit as st
import plotly.graph_objects as go
import utils

def render(forecast_data, card_gap_amt, other_income, deduction, disallowed):
    st.subheader("📝 2025년 귀속 종합소득세 시뮬레이션")
    
    # Tab 1에서 계산된 값 가져오기
    final_rev_baseline = forecast_data['final_rev_baseline']
    proj_expense_simple = forecast_data['proj_expense_simple']
    months_passed = forecast_data['months_passed']
    
    scenario = st.select_slider(
        "시나리오 선택",
        options=["S1(극단적 보수)", "S2(보수적)", "S3(합리적 보수)", "S4(전략적)"],
        value="S3(합리적 보수)"
    )
    
    # 시나리오 로직
    if scenario == "S1(극단적 보수)":
        final_rev = final_rev_baseline
        final_exp = proj_expense_simple
        desc = "현재 장부상 비용만 인정 (누락분 0원)"
    elif scenario == "S2(보수적)":
        final_rev = final_rev_baseline
        final_exp = proj_expense_simple + (card_gap_amt * 0.5)
        desc = "카드 누락분의 50%만 반영"
    elif scenario == "S3(합리적 보수)":
        final_rev = final_rev_baseline
        annual_card_gap = card_gap_amt / months_passed * 12
        final_exp = proj_expense_simple + annual_card_gap
        desc = "카드 누락분과 미래 비용을 모두 반영한 현실적 수치 ⭐"
    else: # S4
        annual_card_gap = card_gap_amt / months_passed * 12
        final_rev = final_rev_baseline * 0.95 
        final_exp = proj_expense_simple + annual_card_gap + 4000000
        desc = "매출 감소 + 연말 전략적 지출(+400만)"

    # 세금 계산
    tax_base = final_rev + other_income - final_exp - deduction + disallowed
    if tax_base < 0: tax_base = 0
    calc_tax = utils.calculate_tax(tax_base)
    total_tax = calc_tax * 1.1
    
    # 결과 표시
    c1, c2 = st.columns(2)
    with c1:
        st.metric("예상 납부 세액 (지방세 포함)", f"{total_tax:,.0f} 원")
        st.caption(f"과세표준: {tax_base:,.0f} 원")
        st.info(f"**시나리오:** {desc}")
        
        with st.expander("🔍 산출 근거 상세 보기"):
            st.markdown(f"""
            - **총 수입:** {final_rev + other_income:,.0f} (매출+타소득)
            - **총 비용:** {final_exp:,.0f}
            - **조정사항:** {disallowed - deduction:,.0f} (부인액-공제)
            """)

    with c2:
        fig = go.Figure(go.Waterfall(
            name = "Tax", orientation = "v",
            measure = ["relative", "relative", "relative", "relative", "total", "total"],
            x = ["총매출", "타소득/조정", "비용(예상)", "소득공제", "과세표준", "납부세액"],
            y = [final_rev, other_income+disallowed, -final_exp, -deduction, tax_base, total_tax],
            connector = {"line":{"color":"rgb(63, 63, 63)"}},
            decreasing = {"marker":{"color":"green"}},
            increasing = {"marker":{"color":"red"}},
            totals = {"marker":{"color":"blue"}}
        ))
        st.plotly_chart(fig, use_container_width=True)