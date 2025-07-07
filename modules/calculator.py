# K-Quant-Analyzer/modules/calculator.py

import pandas as pd

class QuantCalculator:
    def __init__(self, fs_data_list, market_data):
        """
        :param fs_data_list: 연도별 재무제표 딕셔너리의 리스트 (DataFetcher가 수집)
        :param market_data: 시장 데이터 딕셔너리 (DataFetcher가 수집)
        """
        # 데이터프레임으로 변환하고, 연도순으로 정렬합니다.
        self.fs_df = pd.DataFrame(fs_data_list).set_index('year').sort_index()
        self.market_data = market_data
        # 계산된 지표를 저장할 딕셔너리
        self.metrics = {}

    def calculate_all(self, pykrx_df=None, ticker=None):
        """모든 퀀트 지표를 계산하는 메인 함수 (pykrx 값 직접 반영 지원)"""
        self._calculate_profitability()
        self._calculate_stability()
        self._calculate_growth()
        self._calculate_cash_flow()
        self._calculate_value()

        # pykrx 데이터프레임에서 공식 값 직접 반영
        if pykrx_df is not None and ticker is not None and ticker in pykrx_df.index:
            pykrx_row = pykrx_df.loc[ticker]
            self.metrics['가치'] = {
                'PER': pykrx_row['PER'],
                'PBR': pykrx_row['PBR'],
                'BPS': pykrx_row['BPS']
            }
            # 수익성(EPS)도 pykrx 값으로 덮어쓰기
            if '수익성' not in self.metrics:
                self.metrics['수익성'] = {}
            self.metrics['수익성']['EPS'] = pykrx_row['EPS']
        return self.metrics

    def _calculate_profitability(self):
        """수익성 지표 계산 - pykrx와 호환되도록 수정"""
        latest = self.fs_df.iloc[-1]
        
        # ROE 계산 (pykrx에서 제공하지 않으므로 내부 계산용)
        roe = (latest['당기순이익'] / latest['자본총계']) * 100 if latest['자본총계'] > 0 else 0
        
        # 영업이익률 계산
        op_margin = (latest['영업이익'] / latest['매출액']) * 100 if latest['매출액'] > 0 else 0
        
        # EPS 계산 (pykrx와 동일한 방식으로 계산)
        market_cap = self.market_data['시가총액']
        eps = latest['당기순이익'] / self.market_data['상장주식수'] if self.market_data['상장주식수'] > 0 else 0
        
        self.metrics['수익성'] = {
            'ROE': roe,
            '영업이익률': op_margin,
            'EPS': eps  # pykrx와 동일한 EPS 계산
        }

    def _calculate_stability(self):
        """안정성 지표 계산"""
        latest = self.fs_df.iloc[-1]
        if latest['자본총계'] > 0:
            debt_ratio = (latest['부채총계'] / latest['자본총계']) * 100
        else:
            debt_ratio = float('inf')
        
        self.metrics['안정성'] = {
            '부채비율 (%)': f"{debt_ratio:.2f}"
        }

    def _calculate_growth(self):
        """성장성 지표 계산 - 전년대비 성장률"""
        if len(self.fs_df) < 2:
            self.metrics['성장성'] = {
                '매출액_성장률': 0,
                '영업이익_성장률': 0,
                '당기순이익_성장률': 0
            }
            return
            
        latest = self.fs_df.iloc[-1]
        previous = self.fs_df.iloc[-2]

        # 매출액 증가율 계산
        if previous['매출액'] != 0 and latest['매출액'] != 0:
            sales_growth = ((latest['매출액'] - previous['매출액']) / abs(previous['매출액'])) * 100
        else:
            sales_growth = 0

        # 영업이익 증가율 계산
        if previous['영업이익'] != 0 and latest['영업이익'] != 0:
            op_growth = ((latest['영업이익'] - previous['영업이익']) / abs(previous['영업이익'])) * 100
        else:
            op_growth = 0

        # 당기순이익 증가율 계산
        if previous['당기순이익'] != 0 and latest['당기순이익'] != 0:
            net_growth = ((latest['당기순이익'] - previous['당기순이익']) / abs(previous['당기순이익'])) * 100
        else:
            net_growth = 0

        self.metrics['성장성'] = {
            '매출액_성장률': sales_growth,
            '영업이익_성장률': op_growth,
            '당기순이익_성장률': net_growth
        }

    def _calculate_cash_flow(self):
        """현금흐름 지표 계산"""
        latest = self.fs_df.iloc[-1]
        cfo = latest['영업활동 현금흐름']
        sales = latest['매출액']
        market_cap = self.market_data['시가총액']
        
        # 매출액 대비 영업현금흐름 비율
        cfo_sales_ratio = (cfo / sales) * 100 if sales > 0 else 0
        
        # 시가총액 대비 영업현금흐름 비율
        cfo_market_cap_ratio = (cfo / market_cap) * 100 if market_cap > 0 else 0
        
        self.metrics['현금흐름'] = {
            'CFO_매출액비율': cfo_sales_ratio,
            'OCF_시가총액비율': cfo_market_cap_ratio
        }

    def _calculate_value(self):
        """가치 지표 계산 - pykrx와 동일한 방식으로 계산"""
        latest_fs = self.fs_df.iloc[-1]
        market_cap = self.market_data['시가총액']
        
        # PER 계산 (pykrx와 동일)
        per = market_cap / latest_fs['당기순이익'] if latest_fs['당기순이익'] > 0 else float('inf')
        
        # PBR 계산 (pykrx와 동일)
        pbr = market_cap / latest_fs['자본총계'] if latest_fs['자본총계'] > 0 else float('inf')
        
        # BPS 계산 (pykrx와 동일)
        bps = latest_fs['자본총계'] / self.market_data['상장주식수'] if self.market_data['상장주식수'] > 0 else 0
        
        self.metrics['가치'] = {
            'PER': per,
            'PBR': pbr,
            'BPS': bps  # pykrx와 동일한 BPS 계산
        }
