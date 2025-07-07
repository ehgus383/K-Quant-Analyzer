# test_data_consistency.py

import pandas as pd
import numpy as np
from datetime import datetime
from pykrx import stock
from modules.calculator import QuantCalculator
from modules.scorer import Scorer

def test_data_consistency():
    """calculator와 pykrx 데이터 간의 정합성 검증"""
    
    print("=== 데이터 정합성 검증 시작 ===\n")
    
    # 1. 테스트용 재무 데이터 생성 (삼성전자 기준)
    fs_data_list = [
        {
            'year': 2024,
            '매출액': 300870903000000,
            '영업이익': 32725961000000,
            '당기순이익': 34451351000000,
            '자본총계': 402192070000000,
            '부채총계': 112339878000000,
            '영업활동 현금흐름': 72982621000000
        },
        {
            'year': 2023,
            '매출액': 258935494000000,
            '영업이익': 6566976000000,
            '당기순이익': 15487100000000,
            '자본총계': 363677865000000,
            '부채총계': 92228115000000,
            '영업활동 현금흐름': 44137427000000
        }
    ]
    
    # 2. 실제 시장 데이터 가져오기
    today = datetime.now().strftime('%Y%m%d')
    print(f"오늘 날짜: {today}")
    
    try:
        # 기본 펀더멘털 데이터
        universe_df = stock.get_market_fundamental_by_ticker(today, market="ALL")
        universe_df = universe_df[(universe_df['PER'] > 0) & (universe_df['PBR'] > 0)]
        
        # 추가 시장 데이터
        market_cap_df = stock.get_market_cap_by_ticker(today, market="ALL")
        
        # 두 데이터프레임 병합
        universe_df = universe_df.join(market_cap_df[['시가총액', '거래량', '거래대금', '상장주식수']], how='inner')
        
        print(f"전체 종목 수: {len(universe_df)}")
        
        # 3. 삼성전자 데이터 추출
        ticker = '005930'
        if ticker in universe_df.index:
            pykrx_data = universe_df.loc[ticker]
            print(f"\n=== pykrx 데이터 (삼성전자) ===")
            print(f"PER: {pykrx_data['PER']:.2f}")
            print(f"PBR: {pykrx_data['PBR']:.2f}")
            print(f"EPS: {pykrx_data['EPS']:,}")
            print(f"BPS: {pykrx_data['BPS']:,}")
            print(f"DIV: {pykrx_data['DIV']:.2f}")
            print(f"시가총액: {pykrx_data['시가총액']:,}")
            print(f"상장주식수: {pykrx_data['상장주식수']:,}")
            
            # 4. calculator로 계산
            market_data = {
                '시가총액': pykrx_data['시가총액'],
                '상장주식수': pykrx_data['상장주식수']
            }
            
            calculator = QuantCalculator(fs_data_list, market_data)
            calculated_metrics = calculator.calculate_all()
            
            print(f"\n=== calculator 계산 결과 ===")
            print(f"가치 지표:")
            for key, value in calculated_metrics['가치'].items():
                print(f"  {key}: {value:.2f}")
            
            print(f"\n수익성 지표:")
            for key, value in calculated_metrics['수익성'].items():
                if isinstance(value, float):
                    print(f"  {key}: {value:.2f}")
                else:
                    print(f"  {key}: {value}")
            
            # 5. 데이터 정합성 검증
            print(f"\n=== 데이터 정합성 검증 ===")
            
            # PER 비교
            pykrx_per = pykrx_data['PER']
            calc_per = calculated_metrics['가치']['PER']
            per_diff = abs(pykrx_per - calc_per) / pykrx_per * 100 if pykrx_per != 0 else 0
            print(f"PER 차이: pykrx={pykrx_per:.2f}, calculator={calc_per:.2f}, 차이율={per_diff:.2f}%")
            
            # PBR 비교
            pykrx_pbr = pykrx_data['PBR']
            calc_pbr = calculated_metrics['가치']['PBR']
            pbr_diff = abs(pykrx_pbr - calc_pbr) / pykrx_pbr * 100 if pykrx_pbr != 0 else 0
            print(f"PBR 차이: pykrx={pykrx_pbr:.2f}, calculator={calc_pbr:.2f}, 차이율={pbr_diff:.2f}%")
            
            # EPS 비교
            pykrx_eps = pykrx_data['EPS']
            calc_eps = calculated_metrics['수익성']['EPS']
            eps_diff = abs(pykrx_eps - calc_eps) / pykrx_eps * 100 if pykrx_eps != 0 else 0
            print(f"EPS 차이: pykrx={pykrx_eps:,}, calculator={calc_eps:,.0f}, 차이율={eps_diff:.2f}%")
            
            # BPS 비교
            pykrx_bps = pykrx_data['BPS']
            calc_bps = calculated_metrics['가치']['BPS']
            bps_diff = abs(pykrx_bps - calc_bps) / pykrx_bps * 100 if pykrx_bps != 0 else 0
            print(f"BPS 차이: pykrx={pykrx_bps:,}, calculator={calc_bps:,.0f}, 차이율={bps_diff:.2f}%")
            
            # 6. Scorer 테스트
            print(f"\n=== Scorer 테스트 ===")
            scorer = Scorer(ticker, calculated_metrics, universe_df)
            final_score, category_scores, comment = scorer.get_final_score()
            
            print(f"최종 점수: {final_score:.1f}점")
            print(f"카테고리별 점수:")
            for category, score in category_scores.items():
                print(f"  {category}: {score:.1f}점")
            print(f"평가: {comment}")
            
            # 7. 정합성 평가
            print(f"\n=== 정합성 평가 ===")
            max_diff = max(per_diff, pbr_diff, eps_diff, bps_diff)
            if max_diff < 5.0:
                print("✅ 데이터 정합성 우수 (차이율 < 5%)")
            elif max_diff < 10.0:
                print("⚠️ 데이터 정합성 양호 (차이율 < 10%)")
            else:
                print("❌ 데이터 정합성 문제 (차이율 >= 10%)")
                print("   원인 분석 필요: 계산 방식, 데이터 소스, 시점 차이 등")
            
        else:
            print(f"❌ {ticker} 데이터를 찾을 수 없습니다.")
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    test_data_consistency() 