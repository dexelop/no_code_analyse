import streamlit as st
import utils  # 같은 폴더에 있는 utils.py 임포트

def render(card_gap_amt, missing_df, api_key):
    st.subheader("신용카드 미처리 내역 (Gap Analysis)")
    
    c1, c2 = st.columns([3, 1])
    
    with c1:
        st.error(f"🚨 **총 누락 의심 금액 (확정전표 기준): {card_gap_amt:,.0f} 원**")
        
        if not missing_df.empty:
            # 필터링 기능
            status_options = missing_df['전표상태'].unique()
            status_filter = st.multiselect("전표 상태 필터", options=status_options, default=['확정', '확정가능'])
            
            filtered_df = missing_df[missing_df['전표상태'].isin(status_filter)]
            
            # 데이터프레임 표시
            display_cols = ['일자', '거래처', '업종(업태/종목)', '금액', '비고(AI힌트)']
            st.dataframe(
                filtered_df[display_cols].sort_values('금액', ascending=False).head(200),
                width=1000
            )
        else:
            st.write("누락된 내역이 없거나 데이터가 매칭되었습니다.")
            
    with c2:
        st.markdown("#### 🤖 AI 정밀 분석")
        st.info("전년도 이력과 업종 정보를 기반으로 계정과목을 추천합니다.")
        if st.button("미분류 내역 AI 분석"):
            if api_key:
                cols_to_ai = ['거래처', '업종(업태/종목)', '금액', '전표상태', '전년도이력']
                # 상위 10개 샘플 분석
                sample_data = missing_df[cols_to_ai].head(10).to_dict(orient='records') if not missing_df.empty else "데이터 없음"
                
                with st.spinner("Gemini 2.0 Flash 분석 중..."):
                    result = utils.categorize_expenses_with_ai(api_key, str(sample_data))
                    st.success("분석 완료!")
                    st.code(result, language='json')
            else:
                st.error("API 키가 설정되지 않았습니다.")