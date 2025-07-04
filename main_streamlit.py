# K-Quant-Analyzer/main_streamlit.py

import streamlit as st
import pandas as pd
from datetime import datetime
from modules.data_fetcher import DataFetcher
from modules.calculator import QuantCalculator
from modules.scorer import Scorer
from pykrx import stock
import plotly.graph_objects as go

@st.cache_data(ttl=86400)
def get_universe_data():
    today = datetime.now().strftime('%Y%m%d')
    # 기본 펀더멘털 데이터
    universe_df = stock.get_market_fundamental_by_ticker(today, market="ALL")
    # PER, PBR 0 이하 제거
    universe_df = universe_df[(universe_df['PER'] > 0) & (universe_df['PBR'] > 0)]
    
    # 추가 시장 데이터 (시가총액, 거래량, 거래대금 등)
    market_cap_df = stock.get_market_cap_by_ticker(today, market="ALL")
    
    # 두 데이터프레임 병합
    universe_df = universe_df.join(market_cap_df[['시가총액', '거래량', '거래대금', '상장주식수']], how='inner')

    # 업종(섹터) 정보 추가 (KOSPI/KOSDAQ 각각 수집 후 합침)
    sector_kospi = stock.get_market_sector_classifications(today, market="KOSPI")
    sector_kosdaq = stock.get_market_sector_classifications(today, market="KOSDAQ")
    sector_df = pd.concat([sector_kospi, sector_kosdaq])
    sector_df = sector_df[['업종명']]
    sector_df.index.name = '티커'
    
    # universe_df와 업종 정보 병합
    universe_df = universe_df.join(sector_df, how='left')
    
    return universe_df

@st.cache_data(ttl=3600)
def run_analysis_cached(ticker_or_name):
    """
    분석 로직을 수행하고 결과를 반환하는 함수 (Streamlit 캐싱 적용)
    """
    try:
        # === 1. 데이터 수집 ===
        fetcher = DataFetcher(ticker_or_name)
        
        current_year = datetime.now().year
        start_year_offset = 1 if datetime.now().month > 3 else 2
        
        fs_data_list = []
        for i in range(3):
            year = current_year - (i + start_year_offset)
            fs_data = fetcher.get_financial_statements(year)
            if fs_data:
                fs_data['year'] = year
                fs_data_list.append(fs_data)
        
        if len(fs_data_list) < 2:
            return None, "오류: 분석에 필요한 최소 2개년치 재무 데이터를 수집하지 못했습니다."

        market_data = fetcher.get_market_data()

        # === 2. 퀀트 지표 계산 ===
        calculator = QuantCalculator(fs_data_list, market_data)
        universe_df = get_universe_data()
        metrics = calculator.calculate_all(pykrx_df=universe_df, ticker=fetcher.ticker)

        # === 3. 점수화 및 평가 ===
        scorer = Scorer(fetcher.ticker, metrics, universe_df)
        final_score, category_scores, comment = scorer.get_final_score()
        
        # === 4. 결과 정리 ===
        results = {
            'corp_name': fetcher.corp_name,
            'ticker': fetcher.ticker,
            'metrics': metrics,
            'category_scores': category_scores,
            'final_score': final_score,
            'comment': comment,
            'price_df': market_data['주가_DF'],
            'fs_data_list': fs_data_list  # 원본 재무 데이터도 포함
        }
        return results, None # 결과와 에러 없음(None)을 반환
    except Exception as e:
        return None, f"분석 중 오류가 발생했습니다: {e}"

def main():
    st.set_page_config(page_title="K-Quant Analyzer", layout="wide")

    st.title("📈 K-Quant Analyzer")
    st.write("DART와 PyKrx 데이터를 활용한 대한민국 상장기업 퀀트 분석 도구입니다.")
    st.write("---")

    # --- 사이드바 ---
    st.sidebar.header("분석 설정")
    universe_df = get_universe_data()
    # 종목명, 업종, 시가총액 필터 UI 추가
    all_corp_names = universe_df.index.tolist()
    all_sectors = sorted(universe_df['업종명'].dropna().unique())
    min_cap, max_cap = int(universe_df['시가총액'].min()), int(universe_df['시가총액'].max())

    # --- 업종 필터 개선: 모두 선택/해제, 검색, 기본값 없음 ---
    if 'selected_sectors' not in st.session_state:
        st.session_state.selected_sectors = []

    def select_all_sectors():
        st.session_state.selected_sectors = all_sectors

    def clear_all_sectors():
        st.session_state.selected_sectors = []

    st.sidebar.write("### 업종 필터")
    col1, col2 = st.sidebar.columns(2)
    with col1:
        st.button("모두 선택", on_click=select_all_sectors)
    with col2:
        st.button("모두 해제", on_click=clear_all_sectors)

    selected_sector = st.sidebar.multiselect(
        "업종(복수 선택 가능)",
        options=all_sectors,
        default=st.session_state.selected_sectors,
        key="selected_sectors"
    )

    # 시가총액 슬라이더 완전 삭제
    # 기업 선택: 직접 입력 (티커 또는 기업명)
    target_input = st.sidebar.text_input("분석할 기업 (티커 또는 기업명, 한글 입력 가능)")
    analyze_button = st.sidebar.button("분석 실행", type="primary")

    # --- 메인 화면 ---
    if analyze_button:
        if not target_input:
            st.error("분석할 기업명을 입력해주세요.")
        else:
            with st.spinner(f"**{target_input}** 기업의 데이터를 수집하고 분석 중입니다... 잠시만 기다려 주세요."):
                results, error_msg = run_analysis_cached(target_input)

            if error_msg:
                st.error(error_msg)
            elif results:
                st.success(f"**{results['corp_name']} ({results['ticker']})** 분석이 완료되었습니다.")
                
                # 데이터 수집 상태 요약
                with st.expander("📊 데이터 수집 상태"):
                    total_years = len(results['fs_data_list'])
                    st.write(f"**수집된 연도**: {total_years}개년")
                    
                    # 필수 데이터 누락 여부 확인
                    missing_data = []
                    for fs_data in results['fs_data_list']:
                        year = fs_data['year']
                        if fs_data['매출액'] == 0:
                            missing_data.append(f"{year}년 매출액")
                        if fs_data['영업이익'] == 0:
                            missing_data.append(f"{year}년 영업이익")
                        if fs_data['당기순이익'] == 0:
                            missing_data.append(f"{year}년 당기순이익")
                    
                    if missing_data:
                        st.warning(f"⚠️ 누락된 데이터: {', '.join(missing_data)}")
                        st.info("일부 지표가 0으로 표시되는 것은 DART에서 해당 계정과목을 찾지 못했기 때문입니다. 이는 해당 기업의 재무제표 구조가 다르거나 특정 연도에 데이터가 없을 수 있습니다.")
                    else:
                        st.success("✅ 모든 필수 데이터가 정상적으로 수집되었습니다.")
                
                st.write("---")

                # 최종 평가 요약
                col1, col2 = st.columns([0.7, 0.3])
                with col1:
                    st.header("📊 최종 평가 요약")
                    st.info(results['comment'])
                with col2:
                    st.metric(label="종합 재무 건전성 점수", value=f"{results['final_score']:.1f} / 100")

                # 카테고리별 점수 및 세부 지표
                st.header("🔍 세부 분석 결과")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("카테고리별 점수 (100점 만점)")
                    # 각 카테고리의 배점 정보 추가
                    category_info = {
                        '가치': {'배점': 20, '설명': 'PBR, PER (낮을수록 좋음)'},
                        '수익성': {'배점': 20, '설명': 'EPS (높을수록 좋음)'},
                        '배당': {'배점': 15, '설명': '배당수익률 (높을수록 좋음)'},
                        '성장잠재력': {'배점': 15, '설명': 'BPS (높을수록 좋음)'},
                        '안정성': {'배점': 15, '설명': '시가총액, 거래량 (높을수록 좋음)'},
                        '성장성': {'배점': 10, '설명': '매출액, 이익 성장률 (높을수록 좋음)'},
                        '현금흐름': {'배점': 5, '설명': '영업활동 현금흐름 (높을수록 좋음)'}
                    }
                    scorer = Scorer(results['ticker'], results['metrics'], get_universe_data())
                    sector_scores = scorer.get_sector_scores()
                    score_data = []
                    for category, score in results['category_scores'].items():
                        info = category_info[category]
                        sector_score = sector_scores.get(category, 0)
                        score_data.append({
                            '카테고리': category,
                            '시장전체점수': score,
                            '동일업종점수': sector_score,
                            '배점': info['배점'],
                            '달성률(시장)': f"{(score/info['배점']*100):.1f}%",
                            '달성률(업종)': f"{(sector_score/info['배점']*100):.1f}%",
                            '설명': info['설명']
                        })
                    score_df = pd.DataFrame(score_data)
                    st.dataframe(
                        score_df.style.format({
                            '시장전체점수': '{:.1f}',
                            '동일업종점수': '{:.1f}',
                            '배점': '{:.0f}',
                            '달성률(시장)': '{}',
                            '달성률(업종)': '{}'
                        })
                    )
                    # --- 지표별 바 차트 시각화 ---
                    st.subheader("카테고리별 점수 바 차트")
                    st.bar_chart(score_df.set_index('카테고리')[['시장전체점수', '동일업종점수']])
                    # --- 레이더 차트(Plotly) ---
                    radar_categories = score_df['카테고리'].tolist()
                    radar_market = score_df['시장전체점수'].tolist()
                    radar_sector = score_df['동일업종점수'].tolist()
                    fig = go.Figure()
                    fig.add_trace(go.Scatterpolar(r=radar_market, theta=radar_categories, fill='toself', name='시장전체점수'))
                    fig.add_trace(go.Scatterpolar(r=radar_sector, theta=radar_categories, fill='toself', name='동일업종점수'))
                    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, max(score_df['배점'])])), showlegend=True, title="카테고리별 점수 레이더 차트")
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    st.subheader("카테고리별 상세 해설")
                    explanations = scorer.get_explanations()
                    for cat, text in explanations.items():
                        with st.expander(f"{cat} 카테고리 해설", expanded=False):
                            st.write(text)

                # 종합 평가 코멘트
                st.header("📝 최종 종합 평가 코멘트")
                final_comment = scorer.get_final_comment()
                st.info(final_comment)
                
                # 주요 지표 상세
                st.header("🔍 세부 분석 결과")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("주요 지표 상세")
                    # 각 카테고리를 expander로 표시
                    for category, values in results['metrics'].items():
                        score = results['category_scores'].get(category, 0)
                        with st.expander(f"**{category}** (점수: {score:.1f})"):
                            for key, val in values.items():
                                st.text(f"- {key}: {val}")
                
                # 주가 차트
                st.write("---")
                st.header("📉 최근 1년 주가 추이")
                st.line_chart(results['price_df']['종가'])

                # 재무 데이터 상태 확인 (디버깅용)
                st.write("---")
                st.header("🔍 재무 데이터 상태 확인")
                with st.expander("재무 데이터 상세 정보"):
                    for i, fs_data in enumerate(results['fs_data_list']):
                        st.subheader(f"{fs_data['year']}년 재무 데이터")
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write("**재무상태표 항목**")
                            balance_sheet_items = ['유동자산', '비유동자산', '자산총계', '유동부채', '비유동부채', '부채총계', '자본금', '이익잉여금', '자본총계']
                            for item in balance_sheet_items:
                                value = fs_data.get(item, 0)
                                if value == 0:
                                    st.write(f"❌ {item}: {value:,} (누락)")
                                else:
                                    st.write(f"✅ {item}: {value:,}")
                        
                        with col2:
                            st.write("**손익계산서 항목**")
                            income_items = ['매출액', '영업이익', '법인세차감전순이익', '당기순이익', '영업활동 현금흐름']
                            for item in income_items:
                                value = fs_data.get(item, 0)
                                if value == 0:
                                    st.write(f"❌ {item}: {value:,} (누락)")
                                else:
                                    st.write(f"✅ {item}: {value:,}")

if __name__ == '__main__':
    main()
