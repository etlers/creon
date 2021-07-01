import time
import win32com.client

g_objCodeMgr = win32com.client.Dispatch("CpUtil.CpCodeMgr")
g_objCpStatus = win32com.client.Dispatch("CpUtil.CpCybos")
g_objCpTrade = win32com.client.Dispatch("CpTrade.CpTdUtil")

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

        return self.code

# 미체결 조회 서비스
class Cp5339:
    def __init__(self):
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


def Reqeust5339():
    bTradeInit = False
    # 연결 여부 체크
    if (g_objCpStatus.IsConnect == 0):
        print("PLUS가 정상적으로 연결되지 않음. ")
        return False
    if (g_objCpTrade.TradeInit(0) != 0):
        print("주문 초기화 실패")
        return False
    bTradeInit = True

    if bTradeInit == False :
        print("TradeInit 실패")
        return False

    # 미체결 통신 object
    obj = Cp5339()

    diOrderList = {}
    orderList = []
    obj.Request5339(diOrderList, orderList)
    # 미체결 종목 리스트 생성
    list_no_contract = []
    for item in orderList:
        list_no_contract.append(item.debugPrint())
    print("[Reqeust5339]미체결 개수 ", len(orderList))

    return list_no_contract