#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from modules.scorer import Scorer
import pandas as pd
from datetime import datetime
from pykrx import stock

def test_scorer():
    # 1. Universe 데이터 가져오기
    today = datetime.now().strftime('%Y%m%d')
    universe_df = stock.get_market_fundamental_by_ticker(today, market='ALL')
    universe_df = universe_df[(universe_df['PER'] > 0) & (universe_df['PBR'] > 0)]
    
    print(f"Universe 데이터: {universe_df.shape[0]}개 종목")
    print(f"컬럼: {universe_df.columns.tolist()}")
    
    # 2. 테스트용 메트릭스 (삼성전자 기준)
    test_metrics = {
        'PER': 15.0,
        'PBR': 1.2, 
        'EPS': 1000,
        'DIV': 2.5,
        'BPS': 50000
    }
    
    # 3. Scorer 테스트
    scorer = Scorer('005930', test_metrics, universe_df)
    score, categories, comment = scorer.get_final_score()
    
    print("\n=== 테스트 결과 ===")
    print(f"최종 점수: {score:.1f}")
    print("카테고리별 점수:")
    for cat, cat_score in categories.items():
        print(f"  {cat}: {cat_score:.1f}")
    print(f"코멘트: {comment}")
    
    # 4. 실제 종목으로 테스트 (삼성전자가 있다면)
    if '005930' in universe_df.index:
        print("\n=== 실제 삼성전자 데이터 ===")
        samsung_data = universe_df.loc['005930']
        print(f"PER: {samsung_data['PER']:.2f}")
        print(f"PBR: {samsung_data['PBR']:.2f}")
        print(f"EPS: {samsung_data['EPS']}")
        print(f"DIV: {samsung_data['DIV']:.2f}")
        print(f"BPS: {samsung_data['BPS']}")

if __name__ == "__main__":
    test_scorer() 