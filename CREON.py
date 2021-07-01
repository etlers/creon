import sys
import win32com.client
 
# 설명: 주식 계좌잔고 종목(최대 200개)을 가져와 현재가  실시간 조회하는 샘플
# CpEvent: 실시간 현재가 수신 클래스
# CpStockCur : 현재가 실시간 통신 클래스
# Cp6033 : 주식 잔고 조회
# CpMarketEye: 복수 종목 조회 서비스 - 200 종목 현재가를 조회 함.
 
 
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
        # 잔고 저장
        list_jango = []
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
            list_temp = []
            list_temp.append(code)
            list_temp.append(name)
            list_temp.append(amount)
            list_temp.append(buyPrice)            
            # 최종 리스트에 데이터 저장
            list_jango.append(list_temp)
            
        # 인자로 넘겨주기
        return list_jango
 
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
 
 
# CpMarketEye : 복수종목 현재가 통신 서비스
class CpMarketEye:
    def Request(self, codes, rqField):
        # 연결 여부 체크
        objCpCybos = win32com.client.Dispatch("CpUtil.CpCybos")
        bConnect = objCpCybos.IsConnect
        if (bConnect == 0):
            print("PLUS가 정상적으로 연결되지 않음. ")
            return False
 
        # 관심종목 객체 구하기
        objRq = win32com.client.Dispatch("CpSysDib.MarketEye")
        # 요청 필드 세팅 - 종목코드, 종목명, 시간, 대비부호, 대비, 현재가, 거래량
        # rqField = [0,17, 1,2,3,4,10]
        objRq.SetInputValue(0, rqField) # 요청 필드
        objRq.SetInputValue(1, codes)  # 종목코드 or 종목코드 리스트
        objRq.BlockRequest()
 
 
        # 현재가 통신 및 통신 에러 처리
        rqStatus = objRq.GetDibStatus()
        rqRet = objRq.GetDibMsg1()
        print("통신상태", rqStatus, rqRet)
        if rqStatus != 0:
            return False
 
        cnt  = objRq.GetHeaderValue(2)

        # jango_yaml_file = open(jango_yaml_path, 'w', encoding="utf-8")
 
        for i in range(cnt):
            rpCode = objRq.GetDataValue(0, i)  # 코드
            rpTime= objRq.GetDataValue(1, i)  # 시간
            rpDiffFlag = objRq.GetDataValue(2, i)  # 대비부호
            rpDiff = objRq.GetDataValue(3, i)  # 대비
            rpCur = objRq.GetDataValue(4, i)  # 현재가
            rpVol = objRq.GetDataValue(5, i)  # 거래량
            rpName = objRq.GetDataValue(6, i)  # 종목명
            print(rpCode, rpName, rpTime,  rpDiffFlag, rpDiff, rpCur, rpVol)
 
        return True
 

def execute():
    isSB = False
    objCur = []
    
    if isSB:
        cnt = len(objCur)
        for i in range(cnt):
            objCur[i].Unsubscribe()
        print(cnt, "종목 실시간 해지되었음")
    isSB = False

    objCur = []
    codes = []
    obj6033 = Cp6033()
    if obj6033.Request(codes) == False:
        return

    print("잔고 종목 개수:", len(codes))

    # 요청 필드 배열 - 종목코드, 시간, 대비부호 대비, 현재가, 거래량, 종목명
    rqField = [0, 1, 2, 3, 4, 10, 17]  #요청 필드
    objMarkeyeye = CpMarketEye()
    if (objMarkeyeye.Request(codes, rqField) == False):
        exit()

    isSB = True


if __name__ == "__main__":
    execute()
