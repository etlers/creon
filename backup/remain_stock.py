import sys
from PyQt5.QtWidgets import *
import win32com.client

dict_sell_info = {}

# Cp6033 : 주식 잔고 조회
class Cp6033:
    def __init__(self):
        # 통신 OBJECT 기본 세팅
        self.objTrade = win32com.client.Dispatch("CpTrade.CpTdUtil")
        initCheck = self.objTrade.TradeInit(0)
        if (initCheck != 0):
            print("주문 초기화 실패")
            return
 
        # 
        acc = self.objTrade.AccountNumber[0]  # 계좌번호
        accFlag = self.objTrade.GoodsList(acc, 1)  # 주식상품 구분
        print(acc, accFlag[0])
 
        self.objRq = win32com.client.Dispatch("CpTrade.CpTd6033")
        self.objRq.SetInputValue(0, acc)  # 계좌번호
        self.objRq.SetInputValue(1, accFlag[0])  # 상품구분 - 주식 상품 중 첫번째
        self.objRq.SetInputValue(2, 50)  #  요청 건수(최대 50)
 
    # 실제적인 6033 통신 처리
    def rq6033(self, retcode):
        self.objRq.BlockRequest()
 
        # 통신 및 통신 에러 처리
        rqStatus = self.objRq.GetDibStatus()
        rqRet = self.objRq.GetDibMsg1()
        print("통신상태", rqStatus, rqRet)
        if rqStatus != 0:
            return False
 
        cnt = self.objRq.GetHeaderValue(7)
        print(cnt)
 
        print("종목코드 종목명 신용구분 체결잔고수량 체결장부단가 평가금액 평가손익")
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
 
            print(code, name, cashFlag, amount, buyPrice, evalValue, evalPerc)

            if len(name.strip()) > 0:
                dict_sell_info[code] = [int(amount), int(buyPrice)]
 
    def Request(self, retCode):
        self.rq6033(retCode)
 
        # 연속 데이터 조회 - 200 개까지만.
        while self.objRq.Continue:
            self.rq6033(retCode)
            print(len(retCode))
            if len(retCode) >= 200:
                break
        # for debug
        size = len(retCode)
        for i in range(size):
            print(retCode[i])
        
        return True
 
if __name__ == "__main__":
    remain = Cp6033()
    codes = ["A067990","A031980"]
    remain.Request(codes)