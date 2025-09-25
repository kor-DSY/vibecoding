import streamlit as st
import pandas as pd
import os
import plotly.express as px

st.set_page_config(layout="wide") # 넓은 레이아웃 사용
st.title("경제활동 데이터 뷰어")

# --- 데이터 로딩 및 전처리 (캐시 사용) ---
@st.cache_data
def load_data():
    # 파일 경로 설정
    current_dir = os.path.dirname(__file__)
    csv_path = os.path.join(current_dir, '경제활동_통합.csv')

    # 인코딩 시도
    encodings = ['utf-8', 'euc-kr', 'cp949']
    df = None
    for encoding in encodings:
        try:
            df = pd.read_csv(csv_path, encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
        except FileNotFoundError:
            st.error(f"오류: '{csv_path}' 파일을 찾을 수 없습니다.")
            return None

    if df is None:
        st.error("데이터 파일을 읽는데 실패했습니다. 인코딩(utf-8, euc-kr, cp949)을 확인해주세요.")
        return None

    # --- 데이터 전처리 ---
    if '지역' in df.columns:
        df['지역'] = df['지역'].replace('계', '전국')

    if '년도' in df.columns:
        df['년도'] = df['년도'].astype(int).astype(str) + '년'

    try:
        required_cols = ['경제활동인구 (천명)', '취업자 (천명)', '실업자 (천명)']
        for col in required_cols:
            if df[col].dtype == 'object':
                df[col] = df[col].str.replace(',', '', regex=False)
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df.dropna(subset=required_cols, inplace=True)

        df['취업률'] = df.apply(lambda row: (row['취업자 (천명)'] / row['경제활동인구 (천명)']) * 100 if row['경제활동인구 (천명)'] > 0 else 0, axis=1).round(2)
        df['실업률'] = df.apply(lambda row: (row['실업자 (천명)'] / row['경제활동인구 (천명)']) * 100 if row['경제활동인구 (천명)'] > 0 else 0, axis=1).round(2)
    except KeyError as e:
        st.warning(f"경고: {e} 컬럼이 없어 취업/실업률을 계산할 수 없습니다.")
    except Exception as e:
        st.warning(f"경고: 취업/실업률 계산 중 오류 발생: {e}")

    return df

df_original = load_data()

if df_original is None:
    st.stop()

# 지역 필터
if '지역' in df_original.columns:
    unique_regions = sorted(df_original['지역'].unique())
    # '전국'을 필터 옵션에서 제외
    region_options = [r for r in unique_regions if r != '전국']
    
    selected_regions = st.sidebar.multiselect(
        '지역 선택',
        options=region_options,
        default=region_options # 모든 지역을 기본으로 선택
    )
else:
    selected_regions = []
    st.sidebar.warning("'지역' 컬럼을 찾을 수 없습니다.")

if '년도' in df_original.columns:
    unique_years = sorted(df_original['년도'].unique(), reverse=True)
    year_options = ['전체'] + unique_years
    selected_year_option = st.sidebar.selectbox('년도 선택', options=year_options, index=0)
else:
    selected_year_option = '전체'
    st.sidebar.warning("'년도' 컬럼을 찾을 수 없습니다.")

# --- 데이터 필터링 ---
df_filtered = df_original.copy()

if selected_regions:
    df_filtered = df_filtered[df_filtered['지역'].isin(selected_regions)]

if selected_year_option != '전체':
    df_filtered = df_filtered[df_filtered['년도'] == selected_year_option]

# --- 전국 데이터 요약 표시 ---
st.write("---")
nationwide_df = df_original[df_original['지역'] == '전국']
if not nationwide_df.empty and all(c in nationwide_df.columns for c in ['년도', '취업률', '실업률']):
    nationwide_df_sorted = nationwide_df.set_index('년도').sort_index()
    num_years = len(nationwide_df_sorted.index.unique())
    st.write(f"#### 최근 {num_years}년간 전국의 취업률과 실업률")

    col1, col2 = st.columns(2)
    with col1:
        fig_emp_summary = px.bar(nationwide_df_sorted, y='취업률', text_auto='.2f', title='취업률 (%)')
        fig_emp_summary.update_traces(textposition='outside')
        st.plotly_chart(fig_emp_summary, use_container_width=True)
    with col2:
        fig_unemp_summary = px.bar(nationwide_df_sorted, y='실업률', text_auto='.2f', title='실업률 (%)')
        fig_unemp_summary.update_traces(textposition='outside')
        st.plotly_chart(fig_unemp_summary, use_container_width=True)
st.write("---")

# --- 데이터 표시 ---
if '년도' in df_filtered.columns and '지역' in df_filtered.columns:
    cols = df_filtered.columns.tolist()
    if '년도' in cols: cols.remove('년도')
    if '지역' in cols: cols.remove('지역')
    new_order = ['년도', '지역'] + cols
    df_filtered = df_filtered[new_order]

st.write("#### 검색된 경제활동 데이터", df_filtered)

# --- 차트 표시 ---
st.write("---")

# 동적 제목 생성
if selected_year_option == '전체':
    chart_title_prefix = "연도별"
else:
    chart_title_prefix = selected_year_option

st.write(f"#### {chart_title_prefix} 지역별 비교")

chart_cols = ['년도', '지역', '취업률', '실업률']
if all(col in df_filtered.columns for col in chart_cols):
    if not df_filtered.empty:
        # 취업률 차트 (첫 번째 행)
        try:
            employment_pivot = df_filtered.pivot_table(index='지역', columns='년도', values='취업률')
            fig_emp = px.bar(employment_pivot, barmode='group', text_auto='.2f', title=f"{chart_title_prefix} 지역별 취업률")
            fig_emp.update_traces(textposition='outside')
            st.plotly_chart(fig_emp, use_container_width=True)
        except Exception as e:
            st.warning(f"취업률 차트를 그릴 수 없습니다: {e}")

        # 실업률 차트 (두 번째 행)
        try:
            unemployment_pivot = df_filtered.pivot_table(index='지역', columns='년도', values='실업률')
            fig_unemp = px.bar(unemployment_pivot, barmode='group', text_auto='.2f', title=f"{chart_title_prefix} 지역별 실업률")
            fig_unemp.update_traces(textposition='outside')
            st.plotly_chart(fig_unemp, use_container_width=True)
        except Exception as e:
            st.warning(f"실업률 차트를 그릴 수 없습니다: {e}")
    else:
        st.warning("선택된 조건에 해당하는 데이터가 없습니다.")
else:
    st.info("취업률/실업률 그래프를 표시하려면 데이터에 '년도', '지역', '취업률', '실업률' 열이 포함되어야 합니다.")
