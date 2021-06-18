import time
import yaml
import sys
import requests
from bs4 import BeautifulSoup as bs
import win32com.client
import quick_news as NEWS

sys.path.append("C:/Users/etlers/Documents/project/python/common")

import date_util as DU
import conn_db as DB

# 파일 경로
result_txt_file = './txt/creon_deal.txt'
quant_high_yaml_file = './config/quant_high.yaml'
jongmok_yaml_file = './config/jongmok.yaml'
jongmok_list_csv_file = 'C:/Users/etlers/Documents/project/CSV/jongmok_list.csv'
# 주문내역 저장할 텍스르 파일
txt_file = open(result_txt_file, 'w')

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
# 조건 데이터 추출쿼리 및 변수
from_up_vol_rt = query_param["from_up_vol_rt"]
to_up_vol_rt = query_param["to_up_vol_rt"]
from_price = query_param["from_price"]
to_price = query_param["to_price"]
from_up_prc_rt = query_param["from_up_prc_rt"]
to_up_prc_rt = query_param["to_up_prc_rt"]
vol = query_param["vol"]
# 대상 추출 쿼리
extract_qry = f"""
SELECT JONGMOK_CD
     , JONGMOK_NM
     , PRC
  FROM (SELECT JONGMOK_CD, JONGMOK_NM
		       , PRC
		       , ROUND(((PRC - PRE_PRC) / PRE_PRC) * 100 , 2) AS GAP_PRC_RT
		       , VOL
		       , ROUND(((VOL - PRE_VOL) / PRE_VOL) * 100 , 2) AS GAP_VOL_RT
		    FROM (SELECT *
		               , LAG(PRC, 3) OVER(PARTITION BY JONGMOK_CD ORDER BY TM) AS PRE_PRC
		               , LAG(VOL, 3) OVER(PARTITION BY JONGMOK_CD ORDER BY TM) AS PRE_VOL
		            FROM creon_quant
				   WHERE 1 = 1
                     AND PRC BETWEEN {from_price} AND {to_price}
                     AND VOL > {vol}) T1
		   WHERE 1 = 1
			  AND TM = (SELECT MAX(TM) FROM creon_quant)) TT
 WHERE 1 = 1
   AND GAP_PRC_RT BETWEEN {from_up_prc_rt} AND {to_up_prc_rt}
   AND GAP_VOL_RT BETWEEN {from_up_vol_rt} AND {to_up_vol_rt}
 ORDER BY GAP_PRC_RT DESC, GAP_VOL_RT DESC
 LIMIT 3
"""

# 종목 명칭, 코드 딕셔너리
with open(jongmok_yaml_file, encoding="utf-8-sig") as stream:
    try:
        dict_jongmok = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
        print(exc)

# 기본 금액
base_amount = dict_quant["base_amount"]
# 매수종목 수
jongmok_cnt = dict_quant["jongmok_cnt"]
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
# 뉴스속보
list_quick_news = []
# 매수 매도를 위한 종목 코드
dict_sell_info = {}
# 매수한 종목코드 이후 잔고 및 매도에 사용
list_jongmok_cd = []


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
 

# Cp7043 상승률 상위 요청 클래스
class Cp7043:
    def __init__(self):
        # 통신 OBJECT 기본 세팅
        self.objRq = win32com.client.Dispatch("CpSysDib.CpSvrNew7043")
        self.objRq.SetInputValue(0, ord('0')) # 거래소 + 코스닥
        self.objRq.SetInputValue(1, ord('2'))  # 상승
        self.objRq.SetInputValue(2, ord('1'))  # 당일
        self.objRq.SetInputValue(3, 21)  # 전일 대비 상위 순
        self.objRq.SetInputValue(4, ord('1'))  # 관리 종목 제외
        self.objRq.SetInputValue(5, ord('0'))  # 거래량 전체
        self.objRq.SetInputValue(6, ord('0'))  # '표시 항목 선택 - '0': 시가대비
        self.objRq.SetInputValue(7, 0)  #  등락율 시작
        self.objRq.SetInputValue(8, 30)  # 등락율 끝
 
    # 실제적인 7043 통신 처리
    def rq7043(self, retcode):
        self.objRq.BlockRequest()
        # 현재가 통신 및 통신 에러 처리
        rqStatus = self.objRq.GetDibStatus()
        rqRet = self.objRq.GetDibMsg1()
        #print("통신상태", rqStatus, rqRet)
        if rqStatus != 0:
            return False
 
        cnt = self.objRq.GetHeaderValue(0)
        cntTotal  = self.objRq.GetHeaderValue(1)
        #print(cnt, cntTotal)
 
        for i in range(cnt):
            code = self.objRq.GetDataValue(0, i)  # 코드
            retcode.append(code)
            if len(retcode) >=  200:       # 최대 200 종목만,
                break
            name = self.objRq.GetDataValue(1, i)  # 종목명
            diffflag = self.objRq.GetDataValue(3, i)
            diff = self.objRq.GetDataValue(4, i)
            vol = self.objRq.GetDataValue(6, i)  # 거래량
            # print(code, name, diffflag, diff, vol)
 
    def Request(self, retCode):
        self.rq7043(retCode)
 
        # 연속 데이터 조회 - 200 개까지만.
        while self.objRq.Continue:
            self.rq7043(retCode)
            #print(len(retCode))
            if len(retCode) >= 200:
                break
 
        # #7043 상승하락 서비스를 통해 받은 상승률 상위 200 종목
        size = len(retCode)
        # for i in range(size):
        #     print(retCode[i])
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
        #print("통신상태", rqStatus, rqRet)
        if rqStatus != 0:
            return False
 
        cnt  = objRq.GetHeaderValue(2)

        list_whole = []
        for i in range(cnt):
            list_jongmok = []
            list_jongmok.append(objRq.GetDataValue(0, i))
            list_jongmok.append(objRq.GetDataValue(1, i))
            list_jongmok.append(objRq.GetDataValue(2, i))
            list_jongmok.append(objRq.GetDataValue(3, i))
            list_jongmok.append(objRq.GetDataValue(4, i))
            list_jongmok.append(objRq.GetDataValue(5, i))
            list_jongmok.append(objRq.GetDataValue(6, i))
            list_whole.append(list_jongmok)

        # 쿼리 헤더
        header = """
            INSERT INTO creon_quant
            ( JONGMOK_CD, TM, VS_SIGN, VS_PRC, PRC, VOL, JONGMOK_NM, HM )
            VALUES"""
        body = ""
        now_tm = DU.get_now_datetime_string().split(" ")[1].replace(":","")
        # 쿼리 인자 값
        for list_val in list_whole:
            body += f"('{list_val[0]}','{now_tm.zfill(6)}',{list_val[2]},{list_val[3]},{list_val[4]},{list_val[5]},'{list_val[6]}','{str(list_val[1]).zfill(4)}'),"
        # 최종 쿼리
        qry = header + "\n" + body[:len(body)-1]
        # 데이터 디비로 저장
        DB.transaction_data(qry)
        print(qry)
        print("Save Data:", DU.get_now_datetime_string())
        
        return True


class quant_jongmok():

    def __init__(self):
        self.isSB = False
        self.objCur = []

    def StopSubscribe(self):
        if self.isSB:
            cnt = len(self.objCur)
            for i in range(cnt):
                self.objCur[i].Unsubscribe()
            #print(cnt, "종목 실시간 해지되었음")
        self.isSB = False
 
        self.objCur = []

    def get_quant_data(self):
        self.StopSubscribe();
        codes = []
        obj7043 = Cp7043()
        if obj7043.Request(codes) == False:
            return
 
        #print("상승종목 개수:", len(codes), ". ", DU.get_now_datetime_string())
 
        # 요청 필드 배열 - 종목코드, 시간, 대비부호 대비, 현재가, 거래량, 종목명
        rqField = [0, 1, 2, 3, 4, 10, 17]  #요청 필드
        objMarkeyeye = CpMarketEye()

        if (objMarkeyeye.Request(codes, rqField) == False):
            exit()

        cnt = len(codes)
        for i in range(cnt):
            self.objCur.append(CpStockCur())
            self.objCur[i].Subscribe(codes[i])

        #print("빼기빼기================-")
        #print(cnt , "종목 실시간 현재가 요청 시작")
        self.isSB = True


# 해당 종목이 뉴스에 있는지 확인
def check_news(jongmok_nm):
    # 뉴스 속보 헤드라인
    for news in list_quick_news:
        # 헤드라인에 있으면
        if jongmok_nm in news:
            return True
    
    return False


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
        self.list_quick_news = NEWS.get_quick_news()
 
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
        #print(cnt)
        idx = 0
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
                idx += 1
                # header
                if i == 1:
                    print("종목코드 종목명 신용구분 체결잔고수량 체결장부단가 평가금액 평가손익")
                # Data
                print(code, name, cashFlag, amount, buyPrice, evalValue, evalPerc)
                # 4.5% 수익률 10원 단위로 매도하기 위한 설정
                prc = int(buyPrice)
                # 매도이익 설정을 위한 저장
                prc = int(int(prc * 1.030) / 10) * 10
                for headline in self.list_quick_news:
                    # 뉴스에 있다면 4.5%
                    if name in headline:
                        prc = int(int(prc * 1.045) / 10) * 10
                        break
                # 딕셔너리에 저장
                dict_sell_info[code] = [int(amount), prc]
 
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


# 매수, 매도
def order_stock(jongmok_cd, div, qty, prc, ho_div, jongmok_nm=""):        
    result_tf = False
    print("#" * 50)
    print("#주문:", jongmok_cd, jongmok_nm, dict_order_div[div], qty, prc, dict_ho_div[ho_div])    
    print("#" * 50)
    # 파일 생성 시에 오류로 종료되면 안되기에 예외처리
    try:
        txt_file.write("# 주문: " + dict_order_div[div])
        txt_file.write("  - " + "\t" + jongmok_cd + "[" + jongmok_nm + "]" + "\t" + format(qty, ",") + "\t" + format(prc, ",") + "\t" + dict_ho_div[ho_div])
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


# 구매한 금액, 수량
def get_buy_price():
    remain = Cp6033()
    remain.Request(list_jongmok_cd)


# 종목 추출 & 매수, 매도 처리
def process_func():

    # 매수 정보 생성 및 주문
    def set_buy_info(jongmok_cd, jongmok_nm, now_price):
        # 시장가 매수를 위한 상한가 10원 단위로 계산한 기준 금액
        base_price = int((now_price * 1.3) / 10) * 10
        # 계산한 매수량
        buy_ea = int(base_amount / base_price)
        # 한 종목에 최대 100주
        if buy_ea > 100:
            buy_ea = 100
        # 시장가 매수
        order_stock(jongmok_cd, "2", buy_ea, 0, "03", jongmok_nm)
    
    # 추출한 데이터
    list_extract_data = DB.query_data(extract_qry)
    # 없으면 빠져나감
    if len(list_extract_data) == 0:
        print("No Data")
        return False
    # 존재하면 처리로 들어감  
    for list_data in list_extract_data:
        # 종목코드가 없을 수도 있기에 예외처리
        try:
            jongmok_cd = list_data[0]
            jongmok_nm = list_data[1]
            now_price = list_data[2]
            # 매수
            set_buy_info(jongmok_cd, jongmok_nm, now_price)
        except Exception as e:
            print("list_extract_data Exception:", e)

    # 구매가 끝났으면 매도 진행. 바로 던지면 매수 전이라 매도 주문이 성사가 안됨
    time.sleep(5)
    # 잔고 요청
    get_buy_price()
    print("#" * 50)
    print(dict_sell_info)
    print("#" * 50)
    # 보유한 주식 매도
    for key, list_val in dict_sell_info.items():
        if list_val[0] == 0: continue
        try:
            order_stock(key, "1", list_val[0], list_val[1], "01")
        except Exception as e:
            print("dict_sell_info Exception:", e)
    
    return True


# 프로그램 시작
if __name__ == "__main__":

    # 종목 코드, 명칭 딕셔너리 생성
    # make_jongmok_dict()

    # 시간 내에 매도를 못 했다면 시가 정리매도 진행
    def sell_all_stokcs():
        # 잔고 요청
        get_buy_price()
        # 보유한 주식 매도
        for key, list_val in dict_sell_info.items():
            try:
                # 시장가 매도
                order_stock(key, "1", list_val[0], 0, "03")
            except Exception as e:
                print("sell_all_stokcs Exception:", e)
        
    # 뉴스속보 추출여부
    quick_news_tf = False
    # 상승률 200 객체 생성
    quant = quant_jongmok()
    # 데이터 초기화
    qry = "TRUNCATE TABLE creon_quant"
    DB.transaction_data(qry)

    idx = 0
    while True:
        now_tm = DU.get_now_datetime_string().split(" ")[1].replace(":","")
        # 9시부터 10초 후에 최초 데이터 저장. 30분 동안만 처리
        if now_tm < start_hms:
            print(now_tm)
            time.sleep(1)
            continue
        elif now_tm > end_hms:
            break
        # 상승률 200 데이터 저장
        quant.get_quant_data()
        idx += 1
        # 세번째 데이터부터 매수를 위한 로직 수행
        if idx > 2:
            if process_func():
                print("매수, 매도 종료")
                break
            time.sleep(8)
        # 대기
        else:
            time.sleep(9)

    # 종료 후에도 데이터는 지정한 시간까지 저장
    print("지정시간 데이터 저장 시작")
    while True:
        now_tm = DU.get_now_datetime_string().split(" ")[1].replace(":","")
        # 적재 지정시간과 잔고 정리 시간이 지나면 종료
        if (now_tm > until_hms and now_tm > clear_hms):
            break
        # 적재 지정시간이 남았으면 상승률 200 데이터 저장
        if now_tm < until_hms:
            quant.get_quant_data()
        else:
            print("잔고정리 대기 중...", now_tm)
        # 1분 단위로
        time.sleep(60)

    # 미체결 리스트를 보관한 자료 구조체
    diOrderList= dict()  # 미체결 내역 딕셔너리 - key: 주문번호, value - 미체결 레코드
    orderList = []       # 미체결 내역 리스트 - 순차 조회 등을 위한 미체결 리스트
    # 미체결 통신 object
    obj = Cp5339()
    diOrderList = {}
    orderList = []
    obj.Request5339(diOrderList, orderList)
    # 미체결 목록
    for item in orderList:
        item.debugPrint()
    print("#" * 50)
    print("[Reqeust5339]미체결 개수 ", len(orderList))
    print("#" * 50)    
    # 주문 취소 통신 object
    objOrder = CpRPOrder()
    # 미체결 전체 취소
    onums = []
    codes = []
    amounts = []
    callback = None
    for item in orderList :
        onums.append(item.orderNum)
        codes.append(item.code)
        amounts.append(item.amount)
    # 미체결 주문번호 개수만큼 취소요청
    for i in range(len(onums)):
        objOrder.BlockRequestCancel(onums[i], codes[i], amounts[i], callback)

    # 잔고 정리시간이 됐으니 잔고가 있으면 시장가로 매도
    sell_all_stokcs()
    # 파일 종료
    txt_file.close()