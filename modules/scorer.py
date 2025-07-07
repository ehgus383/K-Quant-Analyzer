# K-Quant-Analyzer/modules/scorer.py

import numpy as np
import pandas as pd

class Scorer:
    def __init__(self, ticker, metrics, universe_df):
        self.ticker = ticker
        self.metrics = metrics
        self.universe_df = universe_df
        self.weights = {
            '가치': 20,          # PBR, PER 기반
            '수익성': 20,        # EPS 기반
            '배당': 15,          # DIV 기반
            '성장잠재력': 15,    # BPS 기반
            '안정성': 15,        # 시가총액, 거래량 기반
            '성장성': 10,        # 매출액, 이익 성장률 기반
            '현금흐름': 5,       # 영업활동 현금흐름 기반
        }

    def _get_percentile_rank(self, metric_name, lower_is_better=False):
        """pykrx 데이터를 기반으로 백분위 점수를 계산"""
        # pykrx에서 제공하는 컬럼들
        pykrx_columns = ['BPS', 'PER', 'PBR', 'EPS', 'DIV', 'DPS', '시가총액', '거래량', '거래대금', '상장주식수']
        
        # metric_name에서 핵심 키워드 추출
        keywords = ['PBR', 'PER', 'EPS', 'DIV', 'DPS', 'BPS', '시가총액', '거래량', '거래대금', '상장주식수']
        col = None
        
        for key in keywords:
            if key in metric_name:
                if key in self.universe_df.columns:
                    col = key
                    break
        
        if col is None:
            # 직접 매칭 시도
            if metric_name in self.universe_df.columns:
                col = metric_name
            else:
                return 0  # 해당 지표가 없으면 0점
        
        # ticker가 인덱스에 없으면 0점
        if self.ticker not in self.universe_df.index:
            return 0
            
        # universe_df에서 백분위 계산
        series = self.universe_df[col].dropna()  # NaN 값 제거
        if len(series) == 0:
            return 0
            
        target_value = self.universe_df.loc[self.ticker, col]
        if pd.isna(target_value):
            return 0
            
        percentiles = series.rank(pct=True)
        percentile = percentiles.loc[self.ticker]
        
        if lower_is_better:
            score = (1 - percentile) * 100
        else:
            score = percentile * 100
            
        return score

    def _get_sector_percentile_rank(self, metric_name, lower_is_better=False):
        """동일 업종 내 백분위 점수 계산"""
        # 업종명 확인
        if '업종명' not in self.universe_df.columns:
            return 0
        my_sector = self.universe_df.loc[self.ticker, '업종명']
        if pd.isna(my_sector):
            return 0
        sector_df = self.universe_df[self.universe_df['업종명'] == my_sector]
        if len(sector_df) < 5:
            # 업종 내 비교 종목이 너무 적으면 전체 시장 기준 사용
            return self._get_percentile_rank(metric_name, lower_is_better)
        # 기존 백분위 계산과 동일하게 진행
        series = sector_df[metric_name].dropna()
        if len(series) == 0 or self.ticker not in sector_df.index:
            return 0
        target_value = sector_df.loc[self.ticker, metric_name]
        if pd.isna(target_value):
            return 0
        percentiles = series.rank(pct=True)
        percentile = percentiles.loc[self.ticker]
        if lower_is_better:
            score = (1 - percentile) * 100
        else:
            score = percentile * 100
        return score

    def _score_value(self):
        """가치 점수 계산 - PBR, PER, BPS 기반"""
        if '가치' in self.metrics:
            value_metrics = self.metrics['가치']
            
            # pykrx 데이터와 비교하여 백분위 계산
            pbr_score = self._get_percentile_rank('PBR', lower_is_better=True)
            per_score = self._get_percentile_rank('PER', lower_is_better=True)
            bps_score = self._get_percentile_rank('BPS', lower_is_better=False)
            
            # 가중 평균 (PBR, PER이 더 중요)
            return (pbr_score * 0.4 + per_score * 0.4 + bps_score * 0.2)
        
        return 50  # 기본값

    def _score_profitability(self):
        """수익성 점수 계산 - EPS 기반 (pykrx와 동일)"""
        # pykrx의 EPS와 직접 비교
        eps_score = self._get_percentile_rank('EPS', lower_is_better=False)
        
        # 내부 계산된 ROE도 고려 (보조 지표)
        if '수익성' in self.metrics:
            profitability_metrics = self.metrics['수익성']
            if 'ROE' in profitability_metrics:
                roe = profitability_metrics['ROE']
                # ROE는 절대값 기준으로 평가 (0~30% 범위를 0~100점으로)
                roe_score = min(roe * 3.33, 100)  # 30% 이상이면 100점
                # EPS 80%, ROE 20% 가중치
                return eps_score * 0.8 + roe_score * 0.2
        
        return eps_score
    
    def _score_dividend(self):
        """배당 점수 계산 - DIV(배당수익률) 기반"""
        return self._get_percentile_rank('DIV', lower_is_better=False)
    
    def _score_growth_potential(self):
        """성장 잠재력 점수 계산 - BPS 기반 (pykrx와 동일)"""
        # pykrx의 BPS와 직접 비교
        bps_score = self._get_percentile_rank('BPS', lower_is_better=False)
        
        # 내부 계산된 BPS도 확인하여 일치성 검증
        if '가치' in self.metrics:
            value_metrics = self.metrics['가치']
            if 'BPS' in value_metrics:
                # 내부 계산된 BPS와 pykrx BPS가 일치하는지 확인
                internal_bps = value_metrics['BPS']
                # 일치성 검증 로직 (필요시 추가)
                pass
        
        return bps_score
    
    def _score_stability(self):
        """안정성 점수 계산 - 시가총액, 거래량 기반"""
        # 시가총액이 클수록 안정적 (높을수록 좋음)
        market_cap_score = self._get_percentile_rank('시가총액', lower_is_better=False)
        # 거래량이 많을수록 유동성 좋음 (높을수록 좋음)
        volume_score = self._get_percentile_rank('거래량', lower_is_better=False)
        return (market_cap_score + volume_score) / 2
    
    def _score_growth(self):
        """성장성 점수 계산 - 매출액, 이익 성장률 기반"""
        # metrics에서 성장률 데이터 추출
        if '성장성' in self.metrics:
            growth_metrics = self.metrics['성장성']
            scores = []
            
            # 매출액 성장률
            if '매출액_성장률' in growth_metrics:
                # 성장률은 절대값으로 평가 (음수도 양수로 변환하여 평가)
                growth_rate = abs(growth_metrics['매출액_성장률'])
                # 성장률을 백분위로 변환 (임시 기준: 0~50% 범위를 0~100점으로)
                score = min(growth_rate * 2, 100)  # 50% 이상이면 100점
                scores.append(score)
            
            # 영업이익 성장률
            if '영업이익_성장률' in growth_metrics:
                growth_rate = abs(growth_metrics['영업이익_성장률'])
                score = min(growth_rate * 2, 100)
                scores.append(score)
            
            # 당기순이익 성장률
            if '당기순이익_성장률' in growth_metrics:
                growth_rate = abs(growth_metrics['당기순이익_성장률'])
                score = min(growth_rate * 2, 100)
                scores.append(score)
            
            if scores:
                return sum(scores) / len(scores)
        
        return 50  # 기본값
    
    def _score_cash_flow(self):
        """현금흐름 점수 계산 - 영업활동 현금흐름 기반"""
        # metrics에서 현금흐름 데이터 추출
        if '현금흐름' in self.metrics:
            cf_metrics = self.metrics['현금흐름']
            
            # 영업활동 현금흐름 대비 시가총액 비율 (OCF/Market Cap)
            if 'OCF_시가총액비율' in cf_metrics:
                ratio = cf_metrics['OCF_시가총액비율']
                # 비율이 높을수록 좋음 (0~20% 범위를 0~100점으로)
                score = min(ratio * 5, 100)  # 20% 이상이면 100점
                return score
        
        return 50  # 기본값

    def get_final_score(self):
        category_scores = {
            '가치': self._score_value(),
            '수익성': self._score_profitability(),
            '배당': self._score_dividend(),
            '성장잠재력': self._score_growth_potential(),
            '안정성': self._score_stability(),
            '성장성': self._score_growth(),
            '현금흐름': self._score_cash_flow(),
        }
        # 가중치 적용한 최종 점수 계산
        weighted_score = sum(
            category_scores[category] * self.weights[category] / 100
            for category in category_scores.keys()
        )
        comment = f"시장 전체 백분위 기반 상대평가 점수: {weighted_score:.1f}점"
        return weighted_score, category_scores, comment

    def get_sector_scores(self):
        """동일 업종 내 카테고리별 점수 반환 (시장 전체와 동일 구조)"""
        return {
            '가치': self._get_sector_percentile_rank('PBR', lower_is_better=True) * 0.4 +
                  self._get_sector_percentile_rank('PER', lower_is_better=True) * 0.4 +
                  self._get_sector_percentile_rank('BPS', lower_is_better=False) * 0.2,
            '수익성': self._get_sector_percentile_rank('EPS', lower_is_better=False),
            '배당': self._get_sector_percentile_rank('DIV', lower_is_better=False),
            '성장잠재력': self._get_sector_percentile_rank('BPS', lower_is_better=False),
            '안정성': (self._get_sector_percentile_rank('시가총액', lower_is_better=False) +
                    self._get_sector_percentile_rank('거래량', lower_is_better=False)) / 2,
            # 성장성, 현금흐름은 업종 내 상대평가가 어려우므로 전체 시장 기준 사용
            '성장성': self._score_growth(),
            '현금흐름': self._score_cash_flow(),
        }

    def get_explanations(self):
        """
        각 카테고리별 점수 산출 근거와 해설을 반환
        {카테고리: 설명문구} 형태의 딕셔너리 반환
        """
        definitions = {
            '가치': "가치란, 기업의 자산과 이익에 비해 주가가 얼마나 저평가 또는 고평가되어 있는지를 나타냅니다. 일반적으로 PER, PBR이 낮을수록 저평가로 간주되어 투자 매력이 높다고 평가합니다.",
            '수익성': "수익성이란, 기업이 자본과 매출을 얼마나 효율적으로 이익으로 전환하는지를 의미합니다. EPS, ROE, 영업이익률 등이 높을수록 수익성이 우수하다고 평가합니다.",
            '배당': "배당이란, 기업이 이익의 일부를 주주에게 현금 등으로 환원하는 정도를 의미합니다. 배당수익률(DIV), 주당배당금(DPS)이 높을수록 배당 매력이 높다고 평가합니다.",
            '성장잠재력': "성장잠재력이란, 기업이 미래에 자산이나 이익을 얼마나 더 키울 수 있을지를 나타냅니다. BPS(주당순자산)가 높거나 증가세일수록 성장 잠재력이 높다고 평가합니다.",
            '안정성': "안정성이란, 기업이 외부 충격이나 경기 변동에도 버틸 수 있는 재무적 체력을 의미합니다. 시가총액이 크고 거래량이 많을수록 안정성이 높다고 평가합니다.",
            '성장성': "성장성이란, 기업의 매출, 이익 등이 얼마나 빠르게 증가하고 있는지를 의미합니다. 매출액, 영업이익, 당기순이익의 성장률이 높을수록 성장성이 우수하다고 평가합니다.",
            '현금흐름': "현금흐름이란, 기업이 실제로 벌어들이는 현금의 흐름을 의미합니다. 영업활동 현금흐름이 크고, 매출액이나 시가총액 대비 비율이 높을수록 재무적으로 건전하다고 평가합니다."
        }
        explanations = {}
        # 가치
        if '가치' in self.metrics:
            value = self.metrics['가치']
            per = value.get('PER', 'N/A')
            pbr = value.get('PBR', 'N/A')
            bps = value.get('BPS', 'N/A')
            per_score = self._get_percentile_rank('PER', lower_is_better=True)
            pbr_score = self._get_percentile_rank('PBR', lower_is_better=True)
            explanations['가치'] = (
                f"[정의] {definitions['가치']}\n"
                f"PER: {per}, PBR: {pbr}, BPS: {bps}\n"
                f"시장 내 PER 백분위: {per_score:.1f}점, PBR 백분위: {pbr_score:.1f}점. "
                f"PER/PBR이 낮을수록 가치 점수가 높게 산출됩니다."
            )
        # 수익성
        if '수익성' in self.metrics:
            profit = self.metrics['수익성']
            eps = profit.get('EPS', 'N/A')
            roe = profit.get('ROE', 'N/A')
            op_margin = profit.get('영업이익률', 'N/A')
            eps_score = self._get_percentile_rank('EPS', lower_is_better=False)
            explanations['수익성'] = (
                f"[정의] {definitions['수익성']}\n"
                f"EPS: {eps}, ROE: {roe}, 영업이익률: {op_margin}\n"
                f"시장 내 EPS 백분위: {eps_score:.1f}점. "
                f"EPS가 높을수록 수익성 점수가 높게 산출됩니다."
            )
        # 배당
        if '배당' in self.metrics:
            div = self.metrics['배당']
            div_yield = div.get('DIV', 'N/A')
            dps = div.get('DPS', 'N/A')
            div_score = self._get_percentile_rank('DIV', lower_is_better=False)
            explanations['배당'] = (
                f"[정의] {definitions['배당']}\n"
                f"배당수익률(DIV): {div_yield}, 주당배당금(DPS): {dps}\n"
                f"시장 내 배당수익률 백분위: {div_score:.1f}점. "
                f"배당수익률이 높을수록 배당 점수가 높게 산출됩니다."
            )
        # 성장잠재력
        if '가치' in self.metrics:
            value = self.metrics['가치']
            bps = value.get('BPS', 'N/A')
            bps_score = self._get_percentile_rank('BPS', lower_is_better=False)
            explanations['성장잠재력'] = (
                f"[정의] {definitions['성장잠재력']}\n"
                f"BPS: {bps}\n"
                f"시장 내 BPS 백분위: {bps_score:.1f}점. "
                f"BPS가 높을수록 성장잠재력 점수가 높게 산출됩니다."
            )
        # 안정성
        if '안정성' in self.metrics:
            stability = self.metrics['안정성']
            market_cap = stability.get('시가총액', 'N/A')
            volume = stability.get('거래량', 'N/A')
            cap_score = self._get_percentile_rank('시가총액', lower_is_better=False)
            vol_score = self._get_percentile_rank('거래량', lower_is_better=False)
            explanations['안정성'] = (
                f"[정의] {definitions['안정성']}\n"
                f"시가총액: {market_cap}, 거래량: {volume}\n"
                f"시장 내 시가총액 백분위: {cap_score:.1f}점, 거래량 백분위: {vol_score:.1f}점. "
                f"시가총액과 거래량이 높을수록 안정성 점수가 높게 산출됩니다."
            )
        # 성장성
        if '성장성' in self.metrics:
            growth = self.metrics['성장성']
            sales_growth = growth.get('매출액증가율 (%)', 'N/A')
            op_growth = growth.get('영업이익증가율 (%)', 'N/A')
            net_growth = growth.get('당기순이익증가율 (%)', 'N/A')
            explanations['성장성'] = (
                f"[정의] {definitions['성장성']}\n"
                f"매출액증가율: {sales_growth}%, 영업이익증가율: {op_growth}%, 당기순이익증가율: {net_growth}%\n"
                f"성장률이 높을수록 성장성 점수가 높게 산출됩니다."
            )
        # 현금흐름
        if '현금흐름' in self.metrics:
            cash = self.metrics['현금흐름']
            cfo_sales = cash.get('CFO_매출액비율', 'N/A')
            cfo_market = cash.get('OCF_시가총액비율', 'N/A')
            explanations['현금흐름'] = (
                f"[정의] {definitions['현금흐름']}\n"
                f"영업현금흐름/매출액: {cfo_sales:.2f}%, 영업현금흐름/시가총액: {cfo_market:.2f}%\n"
                f"현금흐름 비율이 높을수록 현금흐름 점수가 높게 산출됩니다."
            )
        return explanations

    def get_final_comment(self):
        """
        7~8문장 분량의 종합 평가 코멘트 자동 생성
        """
        # 각 카테고리별 점수와 백분위, 누락 항목, 강점/약점 등을 종합 분석
        scores = self.get_final_score()[1]  # category_scores
        explanations = self.get_explanations()
        comment_lines = []
        # 1. 종목의 전반적 특성
        max_cat = max(scores, key=lambda k: scores[k])
        min_cat = min(scores, key=lambda k: scores[k])
        comment_lines.append(f"이 종목은 '{max_cat}' 측면에서 강점을 보입니다.")
        comment_lines.append(f"반면 '{min_cat}' 카테고리에서는 상대적으로 약점을 가지고 있습니다.")
        # 2. 주요 카테고리별 요약
        for cat in ['가치', '수익성', '성장성', '안정성', '배당', '현금흐름', '성장잠재력']:
            if cat in scores:
                score = scores[cat]
                if score >= 80:
                    comment_lines.append(f"{cat} 점수({score:.1f}점)는 매우 우수한 편입니다.")
                elif score >= 60:
                    comment_lines.append(f"{cat} 점수({score:.1f}점)는 업종 평균 이상입니다.")
                elif score >= 40:
                    comment_lines.append(f"{cat} 점수({score:.1f}점)는 업종 평균 수준입니다.")
                else:
                    comment_lines.append(f"{cat} 점수({score:.1f}점)는 업종 평균에 미치지 못합니다.")
        # 3. 누락/비정상 항목 안내
        missing = [cat for cat in ['가치', '수익성', '성장성', '안정성', '배당', '현금흐름', '성장잠재력'] if cat not in scores]
        if missing:
            comment_lines.append(f"다만 {', '.join(missing)} 항목의 데이터가 누락되어 평가에 한계가 있습니다.")
        # 4. 투자자 관점 종합
        if scores.get('성장성', 0) >= 70:
            comment_lines.append("성장주 투자자에게는 긍정적인 신호로 해석될 수 있습니다.")
        if scores.get('배당', 0) < 30:
            comment_lines.append("배당투자 관점에서는 매력이 다소 떨어집니다.")
        if scores.get('안정성', 0) < 40:
            comment_lines.append("재무적 안정성 측면에서 리스크가 존재할 수 있습니다.")
        # 5. 종합 결론
        comment_lines.append("전반적으로 강점과 약점이 혼재되어 있으니, 투자 목적과 성향에 따라 신중한 판단이 필요합니다.")
        return '\n'.join(comment_lines)
