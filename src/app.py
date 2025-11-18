"""
재무 데이터 분석 Streamlit 앱
"""
import streamlit as st
import pandas as pd
import google.generativeai as genai
from pathlib import Path

# 모듈 임포트
from modules.config import get_api_key, get_default_data_files
from modules.data_loader import (
    load_multiple_json_files,
    load_uploaded_file,
    get_data_info
)


# 페이지 설정
st.set_page_config(
    page_title="재무 데이터 분석",
    page_icon="📊",
    layout="wide"
)


def init_gemini_api(api_key: str):
    """Gemini API 초기화"""
    try:
        genai.configure(api_key=api_key)
        return True
    except Exception as e:
        st.error(f"API 초기화 실패: {e}")
        return False


def main():
    st.title("📊 재무 데이터 분석 대시보드")
    st.markdown("---")

    # Sidebar - 설정
    with st.sidebar:
        st.header("⚙️ 설정")

        # API Key 입력
        default_api_key = get_api_key()
        api_key = st.text_input(
            "Gemini API Key",
            value=default_api_key,
            type="password",
            help=".env 파일에서 자동으로 로드됩니다."
        )

        if api_key:
            if init_gemini_api(api_key):
                st.success("✅ API 연결 성공")
            else:
                st.error("❌ API 연결 실패")
        else:
            st.warning("⚠️ API Key를 입력해주세요")

        st.markdown("---")

        # 데이터 로드 옵션
        st.header("📂 데이터 로드")

        load_option = st.radio(
            "데이터 소스 선택",
            ["디폴트 데이터 (2024, 2025)", "파일 업로드"]
        )

        df = pd.DataFrame()

        if load_option == "디폴트 데이터 (2024, 2025)":
            if st.button("디폴트 데이터 로드"):
                with st.spinner("데이터 로딩 중..."):
                    default_files = get_default_data_files()
                    df = load_multiple_json_files(default_files)

                    if not df.empty:
                        st.session_state['df'] = df
                        st.success(f"✅ 데이터 로드 완료! (총 {len(df):,}행)")
                    else:
                        st.error("❌ 데이터 로드 실패")

        else:  # 파일 업로드
            uploaded_files = st.file_uploader(
                "JSON 파일 업로드",
                type=['json'],
                accept_multiple_files=True,
                help="여러 개의 JSON 파일을 선택할 수 있습니다."
            )

            if uploaded_files:
                with st.spinner("업로드 파일 처리 중..."):
                    dfs = []
                    for uploaded_file in uploaded_files:
                        temp_df = load_uploaded_file(uploaded_file)
                        if not temp_df.empty:
                            dfs.append(temp_df)

                    if dfs:
                        df = pd.concat(dfs, ignore_index=True)
                        st.session_state['df'] = df
                        st.success(f"✅ 업로드 완료! (총 {len(df):,}행)")
                    else:
                        st.error("❌ 업로드 실패")

    # Main Content
    if 'df' in st.session_state and not st.session_state['df'].empty:
        df = st.session_state['df']

        # 탭 생성
        tab1, tab2, tab3 = st.tabs(["📊 데이터 개요", "🔍 데이터 탐색", "🤖 AI 분석"])

        with tab1:
            st.header("데이터 개요")

            # 기본 정보
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("총 행 수", f"{len(df):,}")
            with col2:
                st.metric("총 열 수", len(df.columns))
            with col3:
                # 연도별 데이터 수
                if 'year' in df.columns:
                    year_counts = df['year'].value_counts()
                    st.metric("연도 수", len(year_counts))
            with col4:
                # 메모리 사용량
                memory_mb = df.memory_usage(deep=True).sum() / 1024 / 1024
                st.metric("메모리 사용량", f"{memory_mb:.2f} MB")

            st.markdown("---")

            # 데이터 미리보기
            st.subheader("데이터 미리보기")
            st.dataframe(df.head(100), use_container_width=True)

            # 컬럼 정보
            st.subheader("컬럼 정보")
            col_info = pd.DataFrame({
                '컬럼명': df.columns,
                '데이터 타입': df.dtypes.values,
                '결측치 수': df.isnull().sum().values,
                '고유값 수': [df[col].nunique() for col in df.columns]
            })
            st.dataframe(col_info, use_container_width=True)

        with tab2:
            st.header("데이터 탐색")

            # 필터링 옵션
            st.subheader("데이터 필터링")

            col1, col2 = st.columns(2)

            with col1:
                # 연도 필터
                if 'year' in df.columns:
                    years = sorted(df['year'].unique())
                    selected_years = st.multiselect(
                        "연도 선택",
                        years,
                        default=years
                    )
                    if selected_years:
                        filtered_df = df[df['year'].isin(selected_years)]
                    else:
                        filtered_df = df
                else:
                    filtered_df = df

            with col2:
                # 계정 필터 (계정명이 있는 경우)
                if 'nm_acctit' in df.columns:
                    accounts = sorted(df['nm_acctit'].unique())
                    selected_account = st.selectbox(
                        "계정 선택 (옵션)",
                        ["전체"] + list(accounts)
                    )
                    if selected_account != "전체":
                        filtered_df = filtered_df[filtered_df['nm_acctit'] == selected_account]

            st.markdown("---")

            # 필터링된 데이터 표시
            st.subheader(f"필터링된 데이터 ({len(filtered_df):,}행)")
            st.dataframe(filtered_df, use_container_width=True)

            # 데이터 다운로드
            csv = filtered_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                "📥 CSV 다운로드",
                csv,
                "filtered_data.csv",
                "text/csv",
                key='download-csv'
            )

        with tab3:
            st.header("🤖 AI 분석 (준비 중)")
            st.info("Gemini API를 활용한 데이터 분석 기능이 곧 추가될 예정입니다.")

            if api_key:
                st.write("현재 연결된 API로 다음 기능들을 개발할 수 있습니다:")
                st.markdown("""
                - 📊 데이터 트렌드 분석
                - 💡 인사이트 추출
                - 📈 예측 분석
                - 🔍 이상치 탐지
                """)
            else:
                st.warning("AI 분석을 사용하려면 API Key를 입력해주세요.")

    else:
        # 데이터가 없을 때
        st.info("👈 왼쪽 사이드바에서 데이터를 로드해주세요.")

        # 샘플 정보 표시
        st.markdown("---")
        st.subheader("📋 사용 가능한 데이터")

        default_files = get_default_data_files()
        st.write("**디폴트 데이터 파일:**")
        for file_path in default_files:
            if Path(file_path).exists():
                file_size = Path(file_path).stat().st_size / 1024 / 1024
                st.write(f"- ✅ {file_path.name} ({file_size:.2f} MB)")
            else:
                st.write(f"- ❌ {file_path.name} (파일 없음)")


if __name__ == "__main__":
    main()
