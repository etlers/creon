"""
    쿼리를 읽어 조건에 맞는 데이터가 존재하면 매수 & 매도 처리를 한다
"""
from os import name
import requests
from bs4 import BeautifulSoup as bs
import time, sys, yaml
import win32com.client
import save_rank_news
import save_time_sise
import jango
import no_contract

sys.path.append("C:/Users/etlers/Documents/project/python/common")

import date_util as DU
import conn_db as DB
import send_slack_message as SSM

# 파일 경로
query_deal_yaml_file = './config/query_deal.yaml'
# 환경변수 추출
with open(query_deal_yaml_file) as stream:
    try:
        dict_quant = yaml.safe_load(stream)
        query_param = dict_quant['query_param']
        hms_param = dict_quant['hms_param']
    except yaml.YAMLError as exc:
        print(exc)

# 시간 조건 데이터
start_hms = hms_param["start_hms"]
buy_hms = hms_param["buy_hms"]
sise_hms = hms_param["sise_hms"]
# 추출 조건
from_price = query_param["from_price"]
to_price = query_param["to_price"]
high_rt = query_param["high_rt"]
gap_cnt = query_param["gap_cnt"]
up_cnt = query_param["up_cnt"]
vol = query_param["vol"]
limit = query_param["limit"]
# 기본 금액
base_amount = dict_quant["base_amount"]
# 최대 수량
max_buy_cnt = dict_quant["max_buy_cnt"]
# 이익율
profit_rt = dict_quant["profit_rt"]

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
# 최근 10분 동안 연속 증감
dict_inc_cnt = {}

# 대기. 지정한 시간만큼 대기
def waiting_seconds(sec, msg):
    idx = 0
    while True:
        idx += 1
        if idx > sec: break
        print(DU.get_now_datetime_string(), msg)
        time.sleep(1)


# 매수, 매도
def order_stock(jongmok_cd, div, qty, prc, ho_div, jongmok_nm=""):
    result_tf = False
    print("#" * 50)
    print("#주문:", jongmok_cd, dict_order_div[div], qty, prc, dict_ho_div[ho_div])    
    print("#" * 50)    
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

    return result_tf


# 종목 추출 & 매수, 매도 처리
def order_buy(jongmok_cd, jongmok_nm, now_price):    
    base_price = int((now_price * 1.3) / 10) * 10
    # 계산한 매수량
    buy_ea = int(base_amount / base_price)
    # 한 종목 최대 매수 수량
    if buy_ea > max_buy_cnt:
        buy_ea = max_buy_cnt
    # 시장가 매수
    try:
        order_stock(jongmok_cd, "2", buy_ea, 0, "03", jongmok_nm)
    except Exception as e:
        print("Order Exception:", jongmok_cd, e)


# 잔고내역 생성
def get_jango():
    # 잔고
    creon = jango.Cp6033()
    codes = []
    list_jango = creon.rq6033(codes)

    return list_jango


# 최종 잔고내역 슬랙으로 전송
def send_message():
    # 잔고 요청
    list_jango = get_jango()
    # 메세지 생성
    msg = ""
    try:
        for list_jongmok in list_jango:
            msg += list_jongmok[0] + " " + list_jongmok[1] + "]  " + format(list_jongmok[2], ",") + "  " + format(list_jongmok[3], ",") + "\n"
    except Exception as e:
        print("Send Slack Message Exception:", e)
    
    SSM.send_message_to_slack(msg)


# 단가에 따른 절사 계산
def  calc_sell_prc(in_prc):
    # 수익 설정
    prc = int(in_prc * profit_rt)
    base = 50
    # 단가에 따른 절사 처리
    if prc < 10000:
        nam = prc % 50
        gap = 1
    elif prc < 50000:
        nam = prc % 100
        gap = 2
    elif prc < 100000:
        nam = prc % 500
        gap = 10
    else:
        nam = prc % 1000
        gap = 20
    # 최종 절사금액 생성
    base = base * gap
    if nam < base:
        return int(prc) - nam
    else:
        return int(prc) + base - nam


# 로직 시작
def execute():    
    # 미체결 목록
    list_except_code = no_contract.Reqeust5339()
    # 매수를 위한 추출 쿼리
    extract_qry = f"""
        WITH T2 AS (
        SELECT JONGMOK_CD
             , SUM(POS_CNT) - SUM(NEG_CNT) AS GAP_CNT
             , COUNT(*) AS IN_CNT
          FROM naver_news
         WHERE 1 = 1
           AND JONGMOK_NM <> ARTICLE
         GROUP BY JONGMOK_CD
        )
        SELECT DISTINCT
               T1.JONGMOK_CD
             , T1.JONGMOK_NM
             , T1.END_PRC
          FROM naver_news T1
         INNER JOIN T2
            ON T2.JONGMOK_CD = T1.JONGMOK_CD
         INNER JOIN time_sise T3
            ON T3.JONGMOK_CD = T1.JONGMOK_CD
           AND T3.UP_CNT > {up_cnt}
         WHERE 1 = 1   
           AND T1.JONGMOK_NM <> ARTICLE
           AND T1.END_PRC BETWEEN {from_price} AND {to_price}
         ORDER BY T3.INC_CNT DESC, T2.GAP_CNT DESC, T2.IN_CNT DESC, T1.HIGH_RT, T1.VOL DESC
         LIMIT {limit - len(list_except_code)}
    """
    list_order = DB.query_data(extract_qry)
    # 없으면 종료
    if len(list_order) == 0:
        return False    
    # 매수 주문
    for row in list_order:
        jongmok_cd = row[0]
        jongmok_nm = row[1]
        now_price = row[2]
        # 미체결 종목은 매수에서 제외
        if jongmok_cd in list_except_code: continue
        order_buy(jongmok_cd, jongmok_nm, now_price)
        time.sleep(0.5)
    # 구매가 끝났으면 매도 진행. 바로 던지면 매수 전이라 매도 주문이 성사가 안됨
    waiting_seconds(60, "매도전 매수완료 대기")
    # 잔고 요청
    list_jango = get_jango()
    # 보유한 주식 매도
    for list_jongmok in list_jango:
        # 미체결 종목은 매도에서 제외
        if list_jongmok[0] in list_except_code: continue
        try:
            qty = list_jongmok[2]
            prc = list_jongmok[3]
            prc = calc_sell_prc(prc)
            order_stock(list_jongmok[0], "1", qty, prc, "01")
            time.sleep(1)
        except Exception as e:
            print("Sell Order Exception:", e)
            return False

    return True
    

# 프로그램 시작
if __name__ == "__main__":
    # 시작 대기
    while True:
        now_tm = DU.get_now_datetime_string().split(" ")[1]
        # 시작시간 대기
        if now_tm.replace(":","") < start_hms:
            print("시작대기: ", DU.get_now_datetime_string())
            time.sleep(1)
            continue
        else:
            break
    # 잔고 리스트 생성
    list_jango = get_jango()
    for list_jongmok in list_jango:
        # 장 시작과 동시에 전일까지 보유하고 있는 주식의 매도
        try:
            qty = list_jongmok[2]
            prc = list_jongmok[3]
            prc = calc_sell_prc(prc)
            order_stock(list_jongmok[0], "1", qty, prc, "01")
            time.sleep(0.5)
        except Exception as e:
            print("Sell Order Exception:", e)
    # 뉴스 생성 및 매수 & 매도
    while True:
        # 뉴스 생성
        save_rank_news.execute()
        # 시세 생성
        now_tm = DU.get_now_datetime_string().split(" ")[1]
        if now_tm.replace(":","") < sise_hms:
            print("시세생성 시작대기: ", DU.get_now_datetime_string())
            time.sleep(0.5)
            continue
        # 생성된 뉴스에 해당하는 분단위 시세정보 생성
        save_time_sise.execute()
        # 뉴스 생성 후 매수 & 매도 대기
        now_tm = DU.get_now_datetime_string().split(" ")[1]
        if now_tm.replace(":","") < buy_hms:
            print("매수 & 매도 시작대기: ", DU.get_now_datetime_string())
            time.sleep(0.5)
            continue
        # 로직 시작. 매수, 매도 잘 했으면 종료
        if execute():
            print("매수 & 매도 처리 완료!!")
            break
        # 메세지 찍고 대기 후 다시 뉴스 생성부터 시작
        else:
            print("매수를 위한 조건에 맞는 데이터가 없었음")
            waiting_seconds(60, "재매수를 위한 대기")
    # 슬랙으로 잔고 전송
    send_message()