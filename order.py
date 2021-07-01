from jango import execute
from os import name
import win32com.client

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


# 매수, 매도
def execute(jongmok_cd, div, qty, prc, ho_div):
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


if __name__ == "__main__":
    execute()