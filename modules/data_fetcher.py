# K-Quant-Analyzer/modules/data_fetcher.py

import requests
import pandas as pd
from pykrx import stock
from io import BytesIO
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime

# config.py 파일에서 API 키를 가져오려고 시도합니다.
try:
    from config import DART_API_KEY
except ImportError:
    # 파일이 없거나 키가 설정되지 않은 경우 사용자에게 안내합니다.
    print("오류: config.py 파일이 없거나 DART_API_KEY가 설정되지 않았습니다.")
    print("DART Open API 사이트에서 인증키를 발급받아 config.py 파일에 설정해주세요.")
    DART_API_KEY = None

def get_corp_code_list(api_key):
    """
    DART에 등록된 전체 회사 고유번호 리스트를 다운로드하고 데이터프레임으로 반환합니다.
    이 함수는 프로그램 실행 시 한 번만 호출하면 됩니다.
    """
    print("DART 고유번호 전체 목록을 다운로드합니다...")
    url = f'https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={api_key}'
    res = requests.get(url)
    
    # 받은 zip 파일의 압축을 메모리에서 해제합니다.
    with zipfile.ZipFile(BytesIO(res.content)) as zf:
        # 압축파일 안의 CORPCODE.xml 파일을 엽니다.
        xml_file = zf.open('CORPCODE.xml')
        # XML 파일을 파싱합니다.
        tree = ET.parse(xml_file)
        root = tree.getroot()

    data = []
    # XML의 list 태그를 순회하며 회사 정보를 추출합니다.
    for corp in root.findall('list'):
        # stock_code가 없는 경우 (비상장사)는 제외합니다.
        stock_code_text = corp.findtext('stock_code')
        if stock_code_text is not None:
            stock_code = stock_code_text.strip()
            if stock_code:
                data.append({
                    'corp_code': corp.findtext('corp_code'),
                    'corp_name': corp.findtext('corp_name'),
                    'stock_code': stock_code,
                })
    
    df = pd.DataFrame(data)
    print("다운로드 완료.")
    return df

class DataFetcher:
    """사용자가 입력한 기업의 재무 및 시장 데이터를 수집하는 클래스"""

    def __init__(self, ticker_or_name):
        if DART_API_KEY is None:
            raise ValueError("DART API 키가 설정되지 않았습니다. config.py를 확인해주세요.")
            
        # 클래스가 생성될 때 전체 기업 코드 리스트를 가지고 있도록 합니다.
        self.corp_codes_df = get_corp_code_list(DART_API_KEY)
        
        # 입력된 값이 종목코드인지, 회사명인지 확인하고 필요한 정보들을 찾습니다.
        try:
            if ticker_or_name.isdigit(): # 입력값이 숫자(종목코드)인 경우
                self.ticker = ticker_or_name.zfill(6) # 6자리로 맞춤
                corp_info = self.corp_codes_df[self.corp_codes_df['stock_code'] == self.ticker].iloc[0]
            else: # 입력값이 문자(회사명)인 경우
                corp_info = self.corp_codes_df[self.corp_codes_df['corp_name'] == ticker_or_name].iloc[0]
                self.ticker = corp_info['stock_code']

            self.corp_name = corp_info['corp_name']
            self.corp_code = corp_info['corp_code']
            print(f"분석 대상: {self.corp_name} (종목코드: {self.ticker}, DART 고유번호: {self.corp_code})")
        except IndexError:
            raise ValueError(f"'{ticker_or_name}'에 해당하는 상장기업을 찾을 수 없습니다.")

    def get_financial_statements(self, year):
        """특정 연도의 주요 재무제표(재무상태표, 손익계산서, 현금흐름표) 데이터를 DART에서 가져옵니다."""
        print(f"{year}년 재무제표 수집 중...")
        url = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
        
        # 연결재무제표(CFS)를 우선 조회합니다.
        params = {
            'crtfc_key': DART_API_KEY,
            'corp_code': self.corp_code,
            'bsns_year': str(year),
            'reprt_code': '11011', # 사업보고서
            'fs_div': 'CFS', 
        }
        
        res = requests.get(url, params=params)
        data = res.json()

        # CFS가 없는 경우, 별도/개별재무제표(OFS)로 다시 조회합니다.
        if data.get('status') != '000':
            print(f"[{self.corp_name}] {year}년 연결재무제표(CFS)가 없어, 개별재무제표(OFS)로 조회합니다.")
            params['fs_div'] = 'OFS'
            res = requests.get(url, params=params)
            data = res.json()
            # 그래도 데이터가 없으면 실패 처리합니다.
            if data.get('status') != '000':
                 print(f"[{self.corp_name}] {year}년 재무제표 데이터 수집 실패: {data.get('message')}")
                 return None

        df = pd.DataFrame(data['list'])
        
        # 디버깅: 사용 가능한 계정과목명들을 출력
        print(f"[{self.corp_name}] {year}년 사용 가능한 계정과목들:")
        available_accounts = df['account_nm'].unique()
        for account in sorted(available_accounts):
            print(f"  - {account}")
        
        # 분석에 필요한 주요 계정 과목과 대체 이름들을 정의합니다.
        account_mappings = {
            '유동자산': ['유동자산', '유동자산합계'],
            '비유동자산': ['비유동자산', '비유동자산합계'],
            '자산총계': ['자산총계', '자산총합계', '자산합계'],
            '유동부채': ['유동부채', '유동부채합계'],
            '비유동부채': ['비유동부채', '비유동부채합계'],
            '부채총계': ['부채총계', '부채총합계', '부채합계'],
            '자본금': ['자본금', '주식자본금', '보통주자본금'],
            '이익잉여금': ['이익잉여금', '이익잉여금(결손금)'],
            '자본총계': ['자본총계', '자본총합계', '자본합계', '순자산'],
            '매출액': ['매출액', '매출', '매출금액', '영업수익', '수익(매출액)'],
            '영업이익': ['영업이익', '영업손익', '영업이익(손실)', '계속영업이익(손실)'],
            '법인세차감전순이익': ['법인세차감전순이익', '법인세비용차감전순이익', '법인세비용차감전순이익(손실)'],
            '당기순이익': ['당기순이익', '당기순손익', '순이익', '당기순이익(손실)'],
            '영업활동 현금흐름': ['영업활동 현금흐름', '영업활동으로 인한 현금흐름', '영업활동현금흐름', '영업에서 창출된 현금흐름', '영업으로부터 창출된 현금흐름']
        }
        
        result_fs = {}
        for target_account, possible_names in account_mappings.items():
            found = False
            for account_name in possible_names:
                val_df = df[(df['account_nm'] == account_name)]
                if not val_df.empty:
                    # 'thstrm_amount' (당기금액)을 가져옵니다. 쉼표(,)를 제거하고 숫자로 변환합니다.
                    amount_str = str(val_df.iloc[0]['thstrm_amount'])
                    amount = amount_str.replace(',', '')
                    result_fs[target_account] = int(amount) if amount else 0
                    print(f"[{self.corp_name}] {year}년 {target_account}: {account_name} = {result_fs[target_account]:,}")
                    found = True
                    break
            
            if not found:
                result_fs[target_account] = 0
                print(f"[{self.corp_name}] {year}년 {target_account}: 찾을 수 없음 (대체명: {possible_names})")

        return result_fs

    def get_market_data(self):
        """PyKrx를 이용해 현재 시가총액, 상장주식수 및 최근 1년치 주가 정보를 가져옵니다."""
        print("시장 데이터(시가총액, 주가) 수집 중...")
        today = datetime.now().strftime('%Y%m%d')
        
        # 시가총액 및 상장주식수
        market_cap_df = stock.get_market_cap_by_ticker(today)
        market_cap = market_cap_df.loc[self.ticker, '시가총액']
        shares = market_cap_df.loc[self.ticker, '상장주식수']

        # 주가 (오늘부터 1년 전까지)
        start_date = (datetime.now() - pd.DateOffset(years=1)).strftime('%Y%m%d')
        price_df = stock.get_market_ohlcv_by_date(start_date, today, self.ticker)
        
        return {
            '시가총액': market_cap,
            '상장주식수': shares,
            '주가_DF': price_df
        }
