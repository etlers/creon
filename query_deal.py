import requests
from bs4 import BeautifulSoup as bs
import time, sys, yaml
import win32com.client

sys.path.append("C:/Users/etlers/Documents/project/python/common")

import date_util as DU
import conn_db as DB

# 파일 경로
result_txt_file = './txt/naver_condition_deal.txt'
quant_high_yaml_file = './config/quant_high.yaml'
# 주문내역 저장할 텍스르 파일
txt_file = open(result_txt_file, 'w', encoding="utf-8")

# 환경변수 추출
with open(quant_high_yaml_file) as stream:
    try:
        dict_quant = yaml.safe_load(stream)
        url_param = dict_quant['url_param']
        query_param = dict_quant['query_param']
        hms_param = dict_quant['hms_param']
    except yaml.YAMLError as exc:
        print(exc)

# 시간 조건 데이터
start_hms = hms_param["start_hms"]
end_hms = hms_param["end_hms"]
until_hms = hms_param["until_hms"]
clear_hms = hms_param["clear_hms"]
# 추출 조건
from_price = query_param["from_price"]
to_price = query_param["to_price"]
low_vs_rt = query_param["low_vs_rt"]
gap_low_vs_rt = query_param["gap_low_vs_rt"]
gap_prc_rt = query_param["gap_prc_rt"]
gap_vol_rt = query_param["gap_vol_rt"]
roe = query_param["roe"]
vol = query_param["vol"]
# 기본 금액
base_amount = dict_quant["base_amount"]

# 골든크로스. 단기(20일) 이동평균선이 장기(60일) 이동평균선을 돌파하는 경우의 종목
url_gold = "https://finance.naver.com/sise/item_gold.nhn"
# 갭상승. 갭상승 종목중에서 전일 고가보다 당일 저가가 높은 종
url_gap = "https://finance.naver.com/sise/item_gap.nhn"
# 이격도과열. 당일 주가(현재가)를 이동평균값(20일)으로 나눈 비율이 120%이상 일 경우의 종목
url_igyuk = "https://finance.naver.com/sise/item_igyuk.nhn"
# 상대강도과열. 14일의 상승폭 합/(14 일의 상승폭 합+하락폭 합)의 비율이며 그 비율이 80%이상 일 경우의 종목
url_overheat = "https://finance.naver.com/sise/item_overheating_2.nhn"
# 데이터 추출 URL
list_condition_url = [
    url_igyuk, url_overheat, url_gap, url_gold
]
# 거래량 급증
list_quant_high_url = [
    url_param["sise_quant_high"]["kospi"],
    url_param["sise_quant_high"]["kosdak"]
]
# 저가대비 급등
list_low_up_url = [
    url_param["sise_low_up"]["kospi"],
    url_param["sise_low_up"]["kosdak"]
]
# 전일대비 상승
list_sise_url = [
    url_param["sise_rising"]["kospi"],
    url_param["sise_rising"]["kosdak"]
]

list_jongmok_cd = []

# 매수, 매도 구분
dict_order_div = {
    "1": "매도",
    "2": "매수"
}
# 주문호가 구분코드
dict_ho_div = {
    "01": "보통",
    "03": "시장가",
    "05": "조건부지정가"
}
# 매수 매도를 위한 종목 코드
dict_sell_info = {}

qry_head = """
INSERT INTO naver_condition
(JONGMOK_CD, JONGMOK_NM, PRC, UP_RT, VOL, RNK, POINTS)
VALUES
"""
extract_qry = """
SELECT DISTINCT
       JONGMOK_CD
     , JONGMOK_NM
     , END_PRC
  FROM naver_news
 WHERE 1 = 1
   AND NEG_CNT = 0
   AND POS_CNT > NEG_CNT
   AND HIGH_RT < 95
   AND VOL > 500000
   AND END_PRC < 100000
 ORDER BY POS_CNT DESC, VOL DESC
 LIMIT 3
"""


# Cp6033 : 주식 잔고 조회
class Cp6033:
    def __init__(self):
        # 통신 OBJECT 기본 세팅
        self.objTrade = win32com.client.Dispatch("CpTrade.CpTdUtil")
        initCheck = self.objTrade.TradeInit(0)
        if (initCheck != 0):
            print("주문 초기화 실패")
            return
 
        acc = self.objTrade.AccountNumber[0]  # 계좌번호
        accFlag = self.objTrade.GoodsList(acc, 1)  # 주식상품 구분
        print(acc, accFlag[0])
 
        self.objRq = win32com.client.Dispatch("CpTrade.CpTd6033")
        self.objRq.SetInputValue(0, acc)  # 계좌번호
        self.objRq.SetInputValue(1, accFlag[0])  # 상품구분 - 주식 상품 중 첫번째
        self.objRq.SetInputValue(2, 50)  #  요청 건수(최대 50)

        # 뉴스 속보
        # self.list_quick_news = NEWS.get_quick_news()
 
    # 실제적인 6033 통신 처리
    def rq6033(self, retcode):
        self.objRq.BlockRequest()
 
        # 통신 및 통신 에러 처리
        rqStatus = self.objRq.GetDibStatus()
        rqRet = self.objRq.GetDibMsg1()
        #print("통신상태", rqStatus, rqRet)
        if rqStatus != 0:
            return False
 
        cnt = self.objRq.GetHeaderValue(7)
        for i in range(cnt):
            code = self.objRq.GetDataValue(12, i)  # 종목코드
            name = self.objRq.GetDataValue(0, i)  # 종목명
            retcode.append(code)
            if len(retcode) >=  200:       # 최대 200 종목만,
                break
            cashFlag = self.objRq.GetDataValue(1, i)  # 신용구분
            date = self.objRq.GetDataValue(2, i)  # 대출일
            amount = self.objRq.GetDataValue(7, i) # 체결잔고수량
            buyPrice = self.objRq.GetDataValue(17, i) # 체결장부단가
            evalValue = self.objRq.GetDataValue(9, i) # 평가금액(천원미만은 절사 됨)
            evalPerc = self.objRq.GetDataValue(11, i) # 평가손익
            # 데이터가 정상인 경우
            if len(name.strip()) > 0:
                # header
                if i == 1:
                    print("종목코드 종목명 신용구분 체결잔고수량 체결장부단가 평가금액 평가손익")
                # Data
                print(code, name, cashFlag, amount, buyPrice, evalValue, evalPerc)
                ###################################################################################
                # 수익률 10원 단위로 매도하기 위한 매수가격 추출 및 매도가격 설정
                ###################################################################################
                prc = int(buyPrice)
                # 매도이익 설정을 위한 저장. 기본 2.5% 수익률 지정
                prc = int(int(prc * 1.025) / 10) * 10
                # for headline in self.list_quick_news:
                #     # 뉴스에 있다면 3.5%
                #     if name in headline:
                #         prc = int(int(prc * 1.035) / 10) * 10
                #         break
                # 딕셔너리에 저장
                dict_sell_info[code] = [int(amount), prc]
                ###################################################################################
 
    def Request(self, retCode):
        self.rq6033(retCode)
 
        # 연속 데이터 조회 - 200 개까지만.
        while self.objRq.Continue:
            self.rq6033(retCode)
            #print(len(retCode))
            if len(retCode) >= 200:
                break
        # for debug
        size = len(retCode)
        for i in range(size):
            print(retCode[i])
        return True


# 랭킹에 따른 포인트
def calc_rank_point(rnk):
    if rnk < 4: points = 10
    elif rnk < 10: points = 7
    elif rnk < 21: points = 5
    elif rnk < 31: points = 3
    else: points = 1
    
    return points

# 데이터 타입에 맞게 재생성
def remake_list(list_base, num_cols, rate_cols):    
    for idx in range(len(num_cols)):
        try:
            num = int(list_base[num_cols[idx]].replace(",",""))
        except:
            num = 0
        list_base[num_cols[idx]] = num
    for idx in range(len(rate_cols)):
        try:
            num = float(list_base[rate_cols[idx]].replace(",","").replace("%",""))
        except:
            num = 0
        list_base[rate_cols[idx]] = num
        
    return list_base    

# 급등 데이터 추출
def get_sudden_rising_data(base_url):
    list_whole = []

    response = requests.get( base_url )
    soup = bs(response.text, 'html.parser')    

    content = soup.select("div.box_type_l")
    list_content = str(content).split("\n")
    list_jongmok = []
    for row_data in list_content:
        row = row_data.strip().replace("\t","")
        if '<td class="no">' in row:
            if len(list_jongmok) > 0:
                list_whole.append(list_jongmok)
                list_jongmok = []
        elif "tltle" in row:
            jongmok_cd = row.split("code=")[1].split('"')[0]
            jongmok_nm = row.split("code=")[1].split('"')[1].split('</a')[0].replace(">","")
            list_jongmok.append("A" + jongmok_cd)
            list_jongmok.append(jongmok_nm)
        elif row[:1] != "<":
            list_jongmok.append(row)
        elif ("<td" not in row or row[:4] == "<tr>"):
            continue
        else:
            num_val = row.replace('<td class="number">','')
            if len(num_val) == 0:
                continue
            list_jongmok.append(num_val.replace("</td>",""))

    return list_whole

# 급등 데이터 생성
def get_sudden_rising():

    def make_qry_n_save_data(list_result, list_data_value):     
        body = ""
        rnk = 0
        for list_row in list_result:
            row = "( "
            rnk += 1
            for idx in range(len(list_row)):
                if idx in list_data_value:
                    try:
                        row += "'" + list_row[idx] + "', "
                    except:
                        row += str(list_row[idx]) + ", "
            # 포인트 계산
            points = calc_rank_point(rnk)
            row += str(rnk) + ", " + str(points) + ")," + "\n"
            row = row.replace(", )", ")")
            body += row
        # 저장 쿼리 생성
        ins_qry = qry_head + body
        ins_qry = ins_qry[:len(ins_qry)-2]
        # 디비로 저장
        try:
            DB.transaction_data(ins_qry)
        except Exception as e:
            print("Insert Naver Data Exception:", e)
            print("#"*100)
            print(ins_qry)
            print("#"*100)

    def save_low_up_data():
        num_cols = [3,4,6,7,8,9]
        rate_cols = [0,5,10,11]
        # 등록일시
        ins_dtm = DU.get_now_datetime_string()
        # 코스닥, 코스피 데이터 생성
        for url in list_low_up_url:
            list_whole = get_sudden_rising_data(url)
            
            list_result = []
            for list_row in list_whole:
                if len(list_row) == 12:
                    list_result.append(remake_list(list_row, num_cols, rate_cols))
            list_data_value = [1, 2, 3, 5, 9]
                    
            make_qry_n_save_data(list_result, list_data_value)

    def save_quant_high_data():
        num_cols = [3,4,6,7,8,9]
        rate_cols = [0,5,10]
        # 등록일시
        ins_dtm = DU.get_now_datetime_string()
        # 코스닥, 코스피 데이터 생성
        for url in list_quant_high_url:
            list_whole = get_sudden_rising_data(url)
            
            list_result = []
            for list_row in list_whole:
                if len(list_row) == 11:
                    list_result.append(remake_list(list_row, num_cols, rate_cols))
            list_data_value = [1, 2, 3, 5, 8]
                    
            make_qry_n_save_data(list_result, list_data_value)

    def save_sise_rising():
        num_cols = [2,3,5,6,7,8,9]
        rate_cols = [4,10,11]
        # 등록일시
        ins_dtm = DU.get_now_datetime_string()
        # 코스닥, 코스피 데이터 생성
        for url in list_sise_url:
            list_whole = get_sudden_rising_data(url)
            
            list_result = []
            for list_row in list_whole:
                if len(list_row) == 12:
                    list_result.append(remake_list(list_row, num_cols, rate_cols))
            list_data_value = [0, 1, 2, 4, 5]
                    
            make_qry_n_save_data(list_result, list_data_value)

    # 저가대비 급등
    save_low_up_data()
    # # 거래량 급증
    save_quant_high_data()
    # # 시세 급등
    save_sise_rising()

def get_condition_data(base_url):
    list_whole = []

    response = requests.get( base_url )
    soup = bs(response.text, 'html.parser')    

    content = soup.select("div.box_type_l")
    list_content = str(content).split("\n")
    list_jongmok = []
    for row_data in list_content:
        row = row_data.strip().replace("\t","")
        if '<td class="no">' in row:
            if len(list_jongmok) > 0:
                list_whole.append(list_jongmok)
                list_jongmok = []
        elif "tltle" in row:
            jongmok_cd = row.split("code=")[1].split('"')[0]
            jongmok_nm = row.split("code=")[1].split('"')[1].split('</a')[0].replace(">","")
            list_jongmok.append("A" + jongmok_cd)
            list_jongmok.append(jongmok_nm)
        elif row[:1] != "<":
            list_jongmok.append(row)
        elif ("<td" not in row or row[:4] == "<tr>"):
            continue
        else:
            num_val = row.replace('<td class="number">','')
            if len(num_val) == 0:
                continue
            list_jongmok.append(num_val.replace("</td>",""))

    return list_whole


# 구매한 금액, 수량
def get_buy_price():
    remain = Cp6033()
    remain.Request(list_jongmok_cd)        


# 매수, 매도
def order_stock(jongmok_cd, div, qty, prc, ho_div, jongmok_nm=""):
    result_tf = False
    print("#" * 50)
    print("#주문:", jongmok_cd, dict_order_div[div], qty, prc, dict_ho_div[ho_div])    
    print("#" * 50)
    # 파일 생성 시에 오류로 종료되면 안되기에 예외처리
    try:
        txt_file.write("# 주문: " + dict_order_div[div])
        txt_file.write("  - " + "\t" + jongmok_cd + " [" + jongmok_nm + "]" + "\t" + format(qty, ",") + "\t" + format(prc, ",") + "\t" + dict_ho_div[ho_div] + "\n")
    except Exception as e:
        print("File Write Exception:", e)
    # 매수인 경우 딕셔너리 정보 초기화. 종목코드 넣고 수량, 금액은 '0'으로 설정
    if div == "2":
        dict_sell_info[jongmok_cd] = [0,0]
    
    # 연결 여부 체크
    objCpCybos = win32com.client.Dispatch("CpUtil.CpCybos")
    bConnect = objCpCybos.IsConnect
    if (bConnect == 0):
        print("PLUS가 정상적으로 연결되지 않음. ")
        exit()
    
    # 주문 초기화
    objTrade =  win32com.client.Dispatch("CpTrade.CpTdUtil")
    initCheck = objTrade.TradeInit(0)
    if (initCheck != 0):
        print("주문 초기화 실패")
        exit()
        
    # 주식 매수, 매도 주문
    acc = objTrade.AccountNumber[0] #계좌번호
    accFlag = objTrade.GoodsList(acc, 1)  # 주식상품 구분
    print(acc, accFlag[0])
    objStockOrder = win32com.client.Dispatch("CpTrade.CpTd0311")
    objStockOrder.SetInputValue(0, div)   #  1: 매도, 2: 매수
    objStockOrder.SetInputValue(1, acc )   #  계좌번호
    objStockOrder.SetInputValue(2, accFlag[0])   #  상품구분 - 주식 상품 중 첫번째
    objStockOrder.SetInputValue(3, jongmok_cd)   #  종목코드 - A003540 - 대신증권 종목
    objStockOrder.SetInputValue(4, qty)   #  매도수량
    objStockOrder.SetInputValue(5, prc)   #  주문단가
    objStockOrder.SetInputValue(7, "0")   #  주문 조건 구분 코드, 0: 기본 1: IOC 2:FOK
    objStockOrder.SetInputValue(8, ho_div)   # 주문호가 구분코드 - 01: 보통 03:시장가 05:조건부지정가    
    # 매도 주문 요청
    objStockOrder.BlockRequest()
    # 상태, 결과
    rqStatus = objStockOrder.GetDibStatus()
    rqRet = objStockOrder.GetDibMsg1()

    result_tf = True
    list_jongmok_cd.append(jongmok_cd)

    return result_tf


# 종목 추출 & 매수, 매도 처리
def order_buy(jongmok_cd, jongmok_nm, now_price):    
    base_price = int((now_price * 1.3) / 10) * 10
    # 계산한 매수량
    buy_ea = int(base_amount / base_price)
    # 한 종목에 최대 100주
    if buy_ea > 100:
        buy_ea = 100
    # 시장가 매수
    if order_stock(jongmok_cd, "2", buy_ea, 0, "03", jongmok_nm):
        return True
    else:
        return False


def execute():
    list_order = DB.query_data(extract_qry)
    # 없으면 종료
    if len(list_order) == 0:
        return False

    # 매수 주문
    for row in list_order:
        jongmok_cd = row[0]
        jongmok_nm = row[1]
        now_price = row[2]
        order_buy(jongmok_cd, jongmok_nm, now_price)
        time.sleep(0.5)

    # 구매가 끝났으면 매도 진행. 바로 던지면 매수 전이라 매도 주문이 성사가 안됨
    time.sleep(10)
    # 잔고 요청
    get_buy_price()
    print("#" * 50)
    print(dict_sell_info)
    print("#" * 50)
    # 보유한 주식 매도
    for key, list_val in dict_sell_info.items():
        if list_val[0] == 0: continue
        time.sleep(1)
        try:
            order_stock(key, "1", list_val[0], list_val[1], "01")
        except Exception as e:
            print("dict_sell_info Exception:", e)
            return False

    return True
    

if __name__ == "__main__":

    while True:
        now_tm = DU.get_now_datetime_string().split(" ")[1]
        # 시작시간 대기
        if now_tm.replace(":","") < start_hms:
            print("시작대기: ", DU.get_now_datetime_string())
            time.sleep(1)
            continue
        else:
            break

    buy_tf = execute()
    if buy_tf == False:
        print("매수를 위한 조건에 맞는 데이터가 없었음")
    
    txt_file.close()