# K-Quant-Analyzer/main_console.py

from modules.data_fetcher import DataFetcher
from modules.calculator import QuantCalculator
from modules.scorer import Scorer
from datetime import datetime
import pprint
import pandas as pd
from pykrx import stock

def get_universe_data():
    today = datetime.now().strftime('%Y%m%d')
    universe_df = stock.get_market_fundamental_by_ticker(today, market="ALL")
    universe_df = universe_df[(universe_df['PER'] > 0) & (universe_df['PBR'] > 0)]
    market_cap_df = stock.get_market_cap_by_ticker(today, market="ALL")
    universe_df = universe_df.join(market_cap_df[['시가총액', '거래량', '거래대금', '상장주식수']], how='inner')
    sector_kospi = stock.get_market_sector_classifications(today, market="KOSPI")
    sector_kosdaq = stock.get_market_sector_classifications(today, market="KOSDAQ")
    sector_df = pd.concat([sector_kospi, sector_kosdaq])
    sector_df = sector_df[['업종명']]
    sector_df.index.name = '티커'
    universe_df = universe_df.join(sector_df, how='left')
    return universe_df

def run_analysis(ticker_or_name):
    """분석의 전체 과정을 실행하는 메인 함수"""
    try:
        # === 1. 데이터 수집 ===
        print("-" * 50)
        fetcher = DataFetcher(ticker_or_name)
        
        # 최근 3개년 재무 데이터 수집
        current_year = datetime.now().year
        fs_data_list = []
        # DART는 보통 3월 말에 전년도 사업보고서가 확정됩니다.
        # 따라서 현재 월이 3월 이전이면 2년 전 데이터부터 가져옵니다.
        start_year_offset = 1 if datetime.now().month > 3 else 2
        
        for i in range(3):
            year = current_year - (i + start_year_offset)
            fs_data = fetcher.get_financial_statements(year)
            if fs_data:
                # 계산에 사용할 연도를 함께 저장합니다.
                fs_data['year'] = year
                fs_data_list.append(fs_data)
        
        if len(fs_data_list) < 2: # 성장성 분석을 위해 최소 2개년 데이터 필요
            print("\n오류: 분석에 필요한 최소 2개년치 재무 데이터를 수집하지 못했습니다.")
            return

        market_data = fetcher.get_market_data()

        # === 2. 퀀트 지표 계산 ===
        print("-" * 50)
        print("퀀트 지표 계산 중...")
        calculator = QuantCalculator(fs_data_list, market_data)
        universe_df = get_universe_data()
        metrics = calculator.calculate_all(pykrx_df=universe_df, ticker=fetcher.ticker)

        print("\n" + "="*20 + " 퀀트 지표 분석 결과 " + "="*20)
        pprint.pprint(metrics)

        # === 3. 점수화 및 평가 ===
        print("\n" + "="*20 + " 최종 평가 " + "="*27)
        scorer = Scorer(fetcher.ticker, metrics, universe_df)
        final_score, category_scores, comment = scorer.get_final_score()
        
        print("\n[카테고리별 점수 (100점 만점)]")
        for category, score in category_scores.items():
            print(f"- {category:<6s}: {score:>6.2f}점")

        print("\n[최종 코멘트]")
        print(f"## 최종 재무 건전성 점수: {final_score:.1f} / 100 ##")
        print(f"\n{comment}")
        print("=" * 62)

    except Exception as e:
        print(f"\n프로그램 실행 중 오류가 발생했습니다: {e}")


if __name__ == '__main__':
    # 종목명 또는 종목코드를 입력받아 프로그램을 실행합니다.
    print("K-Quant Analyzer (콘솔 버전)")
    print("가상환경이 활성화되었는지 확인하세요. (터미널에 (venv) 표시)")
    target = input("분석할 기업의 종목명 또는 종목코드를 입력하세요: ")
    if target:
        run_analysis(target)
    else:
        print("입력값이 없습니다. 프로그램을 종료합니다.")