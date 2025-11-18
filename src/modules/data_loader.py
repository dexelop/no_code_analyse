"""
데이터 로더 모듈
JSON 파일을 로드하고 DataFrame으로 변환합니다.
"""
import json
import pandas as pd
from pathlib import Path
from typing import List, Union
import streamlit as st


def load_json_file(file_path: Union[str, Path]) -> pd.DataFrame:
    """
    JSON 파일을 로드하여 DataFrame으로 반환합니다.

    Args:
        file_path: JSON 파일 경로

    Returns:
        pd.DataFrame: 로드된 데이터
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, dict):
            df = pd.DataFrame([data])
        else:
            raise ValueError("지원하지 않는 JSON 형식입니다.")

        return df
    except Exception as e:
        st.error(f"파일 로드 실패: {file_path} - {e}")
        return pd.DataFrame()


def load_multiple_json_files(file_paths: List[Union[str, Path]]) -> pd.DataFrame:
    """
    여러 JSON 파일을 로드하여 하나의 DataFrame으로 병합합니다.

    Args:
        file_paths: JSON 파일 경로 리스트

    Returns:
        pd.DataFrame: 병합된 데이터
    """
    dataframes = []

    for file_path in file_paths:
        if Path(file_path).exists():
            df = load_json_file(file_path)
            if not df.empty:
                dataframes.append(df)
        else:
            st.warning(f"파일을 찾을 수 없습니다: {file_path}")

    if dataframes:
        merged_df = pd.concat(dataframes, ignore_index=True)
        return merged_df
    else:
        return pd.DataFrame()


def load_uploaded_file(uploaded_file) -> pd.DataFrame:
    """
    Streamlit에서 업로드한 파일을 DataFrame으로 변환합니다.

    Args:
        uploaded_file: Streamlit UploadedFile 객체

    Returns:
        pd.DataFrame: 로드된 데이터
    """
    try:
        data = json.load(uploaded_file)

        if isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, dict):
            df = pd.DataFrame([data])
        else:
            raise ValueError("지원하지 않는 JSON 형식입니다.")

        return df
    except Exception as e:
        st.error(f"업로드 파일 로드 실패: {e}")
        return pd.DataFrame()


def get_data_info(df: pd.DataFrame) -> dict:
    """
    DataFrame의 기본 정보를 반환합니다.

    Args:
        df: 데이터프레임

    Returns:
        dict: 데이터 정보 (행 수, 열 수, 컬럼명 등)
    """
    return {
        "총 행 수": len(df),
        "총 열 수": len(df.columns),
        "컬럼명": df.columns.tolist(),
        "메모리 사용량": f"{df.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB"
    }
