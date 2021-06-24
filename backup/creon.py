import time
import win32com.client

g_objCodeMgr = win32com.client.Dispatch('CpUtil.CpCodeMgr')
g_objCpStatus = win32com.client.Dispatch('CpUtil.CpCybos')
g_objCpTrade = win32com.client.Dispatch('CpTrade.CpTdUtil')


# 미체결 주문 정보 저장 구조체
class orderData:
    def __init__(self):
        self.code = ""          # 종목코드
        self.name = ""          # 종목명
        self.orderNum = 0       # 주문번호
        self.orderPrev = 0      # 원주문번호
        self.orderDesc = ""     # 주문구분내용
        self.amount = 0     # 주문수량
        self.price = 0      # 주문 단가
        self.ContAmount = 0  # 체결수량
        self.credit = ""     # 신용 구분 "현금" "유통융자" "자기융자" "유통대주" "자기대주"
        self.modAvali = 0  # 정정/취소 가능 수량
        self.buysell = ""  # 매매구분 코드  1 매도 2 매수
        self.creditdate = ""    # 대출일
        self.orderFlag = ""     # 주문호가 구분코드
        self.orderFlagDesc = "" # 주문호가 구분 코드 내용
 
        # 데이터 변환용
        self.concdic = {"1": "체결", "2": "확인", "3": "거부", "4": "접수"}
        self.buyselldic = {"1": "매도", "2": "매수"}
 
    def debugPrint(self):
        print("%s, %s, 주문번호 %d, 원주문 %d, %s, 주문수량 %d, 주문단가 %d, 체결수량 %d, %s, "
              "정정가능수량 %d, 매수매도: %s, 대출일 %s, 주문호가구분 %s %s"
              %(self.code, self.name, self.orderNum, self.orderPrev, self.orderDesc, self.amount, self.price,
                self.ContAmount,self.credit,self.modAvali, self.buyselldic.get(self.buysell),
                self.creditdate,self.orderFlag, self.orderFlagDesc))


# CpEvent: 실시간 이벤트 수신 클래스
class CpEvent:
    def set_params(self, client):
        self.client = client
 
    def OnReceived(self):
        code = self.client.GetHeaderValue(0)  # 초
        name = self.client.GetHeaderValue(1)  # 초
        timess = self.client.GetHeaderValue(18)  # 초
        exFlag = self.client.GetHeaderValue(19)  # 예상체결 플래그
        cprice = self.client.GetHeaderValue(13)  # 현재가
        diff = self.client.GetHeaderValue(2)  # 대비
        cVol = self.client.GetHeaderValue(17)  # 순간체결수량
        vol = self.client.GetHeaderValue(9)  # 거래량
 
        if (exFlag == ord('1')):  # 동시호가 시간 (예상체결)
            print("실시간(예상체결)", name, timess, "*", cprice, "대비", diff, "체결량", cVol, "거래량", vol)
        elif (exFlag == ord('2')):  # 장중(체결)
            print("실시간(장중 체결)", name, timess, cprice, "대비", diff, "체결량", cVol, "거래량", vol)


# CpStockCur: 실시간 현재가 요청 클래스
class CpStockCur:
    def Subscribe(self, code):
        self.objStockCur = win32com.client.Dispatch("DsCbo1.StockCur")
        handler = win32com.client.WithEvents(self.objStockCur, CpEvent)
        self.objStockCur.SetInputValue(0, code)
        handler.set_params(self.objStockCur)
        self.objStockCur.Subscribe()
 
    def Unsubscribe(self):
        self.objStockCur.Unsubscribe()


# 미체결 조회 서비스
class Cp5339:
    def __init__(self):
        self.bTradeInit = False
        # 연결 여부 체크
        if (g_objCpStatus.IsConnect == 0):
            print("PLUS가 정상적으로 연결되지 않음. ")
            return False
        if (g_objCpTrade.TradeInit(0) != 0):
            print("주문 초기화 실패")
            return False
        self.bTradeInit = True

        self.objRq = win32com.client.Dispatch("CpTrade.CpTd5339")
        self.acc = g_objCpTrade.AccountNumber[0]  # 계좌번호
        self.accFlag = g_objCpTrade.GoodsList(self.acc, 1)  # 주식상품 구분
 
 
    def Request5339(self, dicOrderList, orderList):
        self.objRq.SetInputValue(0, self.acc)
        self.objRq.SetInputValue(1, self.accFlag[0])
        self.objRq.SetInputValue(4, "0") # 전체
        self.objRq.SetInputValue(5, "1") # 정렬 기준 - 역순
        self.objRq.SetInputValue(6, "0") # 전체
        self.objRq.SetInputValue(7, 20) # 요청 개수 - 최대 20개
 
        print("[Cp5339] 미체결 데이터 조회 시작")
        # 미체결 연속 조회를 위해 while 문 사용
        while True :
            ret = self.objRq.BlockRequest()
            if self.objRq.GetDibStatus() != 0:
                print("통신상태", self.objRq.GetDibStatus(), self.objRq.GetDibMsg1())
                return False
 
            if (ret == 2 or ret == 3):
                print("통신 오류", ret)
                return False;
 
            # 통신 초과 요청 방지에 의한 요류 인 경우
            while (ret == 4) : # 연속 주문 오류 임. 이 경우는 남은 시간동안 반드시 대기해야 함.
                remainTime = g_objCpStatus.LimitRequestRemainTime
                print("연속 통신 초과에 의해 재 통신처리 : ",remainTime/1000, "초 대기" )
                time.sleep(remainTime / 1000)
                ret = self.objRq.BlockRequest()
 
 
            # 수신 개수
            cnt = self.objRq.GetHeaderValue(5)
            print("[Cp5339] 수신 개수 ", cnt)
            if cnt == 0 :
                break
 
            for i in range(cnt):
                item = orderData()
                item.orderNum = self.objRq.GetDataValue(1, i)
                item.orderPrev  = self.objRq.GetDataValue(2, i)
                item.code  = self.objRq.GetDataValue(3, i)  # 종목코드
                item.name  = self.objRq.GetDataValue(4, i)  # 종목명
                item.orderDesc  = self.objRq.GetDataValue(5, i)  # 주문구분내용
                item.amount  = self.objRq.GetDataValue(6, i)  # 주문수량
                item.price  = self.objRq.GetDataValue(7, i)  # 주문단가
                item.ContAmount = self.objRq.GetDataValue(8, i)  # 체결수량
                item.credit  = self.objRq.GetDataValue(9, i)  # 신용구분
                item.modAvali  = self.objRq.GetDataValue(11, i)  # 정정취소 가능수량
                item.buysell  = self.objRq.GetDataValue(13, i)  # 매매구분코드
                item.creditdate  = self.objRq.GetDataValue(17, i)  # 대출일
                item.orderFlagDesc  = self.objRq.GetDataValue(19, i)  # 주문호가구분코드내용
                item.orderFlag  = self.objRq.GetDataValue(21, i)  # 주문호가구분코드
 
                # 사전과 배열에 미체결 item 을 추가
                dicOrderList[item.orderNum] = item
                orderList.append(item)
 
            # 연속 처리 체크 - 다음 데이터가 없으면 중지
            if self.objRq.Continue == False :
                print("[Cp5339] 연속 조회 여부: 다음 데이터가 없음")
                break
 
        return True


# 취소 주문 요청에 대한 응답 이벤트 처리 클래스
class CpPB0314:
    def __init__(self, obj) :
        self.name = "td0314"
        self.obj = obj
 
    def Subscribe(self, parent):
        handler = win32com.client.WithEvents(self.obj, CpEvent)
        handler.set_params(self.obj, self.name, parent)


# 주식 주문 취소 클래스
class CpRPOrder:
    def __init__(self):
        self.acc = g_objCpTrade.AccountNumber[0]  # 계좌번호
        self.accFlag = g_objCpTrade.GoodsList(self.acc, 1)  # 주식상품 구분
        self.objCancelOrder = win32com.client.Dispatch("CpTrade.CpTd0314")  # 취소
        self.callback = None
        self.bIsRq = False
        self.RqOrderNum = 0     # 취소 주문 중인 주문 번호
 
    # 주문 취소 통신 - Request 를 이용하여 취소 주문
    # callback 은 취소 주문의 reply 이벤트를 전달하기 위해 필요
    def RequestCancel(self, ordernum, code, amount, callback):
        # 주식 취소 주문
        if self.bIsRq:
            print("RequestCancel - 통신 중이라 주문 불가 ")
            return False
        self.callback = callback
        print("[CpRPOrder/RequestCancel]취소주문", ordernum, code,amount)
        self.objCancelOrder.SetInputValue(1, ordernum)  # 원주문 번호 - 정정을 하려는 주문 번호
        self.objCancelOrder.SetInputValue(2, self.acc)  # 상품구분 - 주식 상품 중 첫번째
        self.objCancelOrder.SetInputValue(3, self.accFlag[0])  # 상품구분 - 주식 상품 중 첫번째
        self.objCancelOrder.SetInputValue(4, code)  # 종목코드
        self.objCancelOrder.SetInputValue(5, amount)  # 정정 수량, 0 이면 잔량 취소임
 
        # 취소주문 요청
        ret = 0
        while True:
            ret = self.objCancelOrder.Request()
            if ret == 0:
                break
 
            print("[CpRPOrder/RequestCancel] 주문 요청 실패 ret : ", ret)
            if ret == 4:
                remainTime = g_objCpStatus.LimitRequestRemainTime
                print("연속 통신 초과에 의해 재 통신처리 : ", remainTime / 1000, "초 대기")
                time.sleep(remainTime / 1000)
                continue
            else:   # 1 통신 요청 실패 3 그 외의 오류 4: 주문요청제한 개수 초과
                return False;
 
 
        self.bIsRq = True
        self.RqOrderNum = ordernum
 
        # 주문 응답(이벤트로 수신
        self.objReply = CpPB0314(self.objCancelOrder)
        self.objReply.Subscribe(self)
        return True
 
    # 취소 주문 - BloockReqeust 를 이용해서 취소 주문
    def BlockRequestCancel(self, ordernum, code, amount, callback):
        # 주식 취소 주문
        self.callback = callback
        print("[CpRPOrder/BlockRequestCancel]취소주문2", ordernum, code,amount)
        self.objCancelOrder.SetInputValue(1, ordernum)  # 원주문 번호 - 정정을 하려는 주문 번호
        self.objCancelOrder.SetInputValue(2, self.acc)  # 상품구분 - 주식 상품 중 첫번째
        self.objCancelOrder.SetInputValue(3, self.accFlag[0])  # 상품구분 - 주식 상품 중 첫번째
        self.objCancelOrder.SetInputValue(4, code)  # 종목코드
        self.objCancelOrder.SetInputValue(5, amount)  # 정정 수량, 0 이면 잔량 취소임
 
        # 취소주문 요청
        ret = 0
        while True:
            ret = self.objCancelOrder.BlockRequest()
            if ret == 0:
                break;
            print("[CpRPOrder/RequestCancel] 주문 요청 실패 ret : ", ret)
            if ret == 4:
                remainTime = g_objCpStatus.LimitRequestRemainTime
                print("연속 통신 초과에 의해 재 통신처리 : ", remainTime / 1000, "초 대기")
                time.sleep(remainTime / 1000)
                continue
            else:   # 1 통신 요청 실패 3 그 외의 오류 4: 주문요청제한 개수 초과
                return False;
 
        print("[CpRPOrder/BlockRequestCancel] 주문결과", self.objCancelOrder.GetDibStatus(), self.objCancelOrder.GetDibMsg1())
        if self.objCancelOrder.GetDibStatus() != 0:
            return False
        return True
 
    # 주문 취소 Request 에 대한 응답 처리
    def OrderReply(self):
        self.bIsRq = False
 
        if self.objCancelOrder.GetDibStatus() != 0:
            print("[CpRPOrder/OrderReply]통신상태",
                  self.objCancelOrder.GetDibStatus(), self.objCancelOrder.GetDibMsg1())
            self.callback.ForwardReply(-1, 0)
            return False
 
        orderPrev = self.objCancelOrder.GetHeaderValue(1)
        code = self.objCancelOrder.GetHeaderValue(4)
        orderNum = self.objCancelOrder.GetHeaderValue(6)
        amount = self.objCancelOrder.GetHeaderValue(5)
 
        print("[CpRPOrder/OrderReply] 주문 취소 reply, 취소한 주문:",orderPrev, code, orderNum, amount)
 
        # 주문 취소를 요청한 클래스로 포워딩 한다.
        if (self.callback != None) :
            self.callback.ForwardReply(0, orderPrev)
