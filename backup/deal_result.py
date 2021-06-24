"""
    거래결과 저장
"""
import sys
from PyQt5.QtWidgets import *
import win32com.client
import ctypes

sys.path.append("C:/Users/etlers/Documents/project/python/common")

import date_util as DU
import conn_db as DB
 
g_objCodeMgr = win32com.client.Dispatch('CpUtil.CpCodeMgr')
g_objCpStatus = win32com.client.Dispatch('CpUtil.CpCybos')
g_objCpTrade = win32com.client.Dispatch('CpTrade.CpTdUtil')
 
def InitPlusCheck():
    # 프로세스가 관리자 권한으로 실행 여부
    if ctypes.windll.shell32.IsUserAnAdmin():
        print('정상: 관리자권한으로 실행된 프로세스입니다.')
    else:
        print('오류: 일반권한으로 실행됨. 관리자 권한으로 실행해 주세요')
        return False
 
    # 연결 여부 체크
    if (g_objCpStatus.IsConnect == 0):
        print("PLUS가 정상적으로 연결되지 않음. ")
        return False
 
    # 주문 관련 초기화
    if (g_objCpTrade.TradeInit(0) != 0):
        print("주문 초기화 실패")
        return False
 
    return True


# 잔고 데이터 리스트
list_jango_data = []

# Cp6032 : 주식 잔고 손익 조회
class Cp6032:
    def __init__(self):
        acc = g_objCpTrade.AccountNumber[0]  # 계좌번호
        accFlag = g_objCpTrade.GoodsList(acc, 1)  # 주식상품 구분
        print(acc, accFlag[0])
 
        self.objRq = win32com.client.Dispatch("CpTrade.CpTd6032")
        self.objRq.SetInputValue(0, acc)  # 계좌번호
        self.objRq.SetInputValue(1, accFlag[0])  # 상품구분 - 주식 상품 중 첫번째
 
    # 실제적인 6032 통신 처리
    def request6032(self):
        sumJango = 0
        sumSellM = 0
        sumRate = 0.0
 
        bIsFist = True
        while True:
            self.objRq.BlockRequest()
            # 통신 및 통신 에러 처리
            rqStatus = self.objRq.GetDibStatus()
            rqRet = self.objRq.GetDibMsg1()
            #print("통신상태", rqStatus, rqRet)
            if rqStatus != 0:
                return False
 
            cnt = self.objRq.GetHeaderValue(0)
            #print('데이터 조회 개수', cnt)
 
            # 헤더 정보는 한번만 처리
            if bIsFist == True:
                sumJango = self.objRq.GetHeaderValue(1)
                sumSellM = self.objRq.GetHeaderValue(2)
                sumRate = self.objRq.GetHeaderValue(3)
                print('잔량평가손익', sumJango, '매도실현손익',sumSellM, '수익률',sumRate)
                bIsFist = False
 
            for i in range(cnt):
                item = {}
                item['종목코드'] = self.objRq.GetDataValue(12, i)  # 종목코드
                item['종목명'] = self.objRq.GetDataValue(0, i)  # 종목명
                item['신용일자'] = self.objRq.GetDataValue(1, i)
                item['전일잔고'] = self.objRq.GetDataValue(2, i)
                item['금일매수수량'] = self.objRq.GetDataValue(3, i)
                item['금일매도수량'] = self.objRq.GetDataValue(4, i)
                item['금일잔고'] = self.objRq.GetDataValue(5, i)
                item['평균매입단가'] = self.objRq.GetDataValue(6, i)
                item['평균매도단가'] = self.objRq.GetDataValue(7, i)
                item['현재가'] = self.objRq.GetDataValue(8, i)
                item['잔량평가손익'] = self.objRq.GetDataValue(9, i)
                item['매도실현손익'] = self.objRq.GetDataValue(10, i)
                item['수익률'] = self.objRq.GetDataValue(11, i)
                print(item)
                list_items = []
                list_items.append(self.objRq.GetDataValue(12, i))
                list_items.append(self.objRq.GetDataValue(0, i))
                list_items.append(self.objRq.GetDataValue(1, i))
                list_items.append(self.objRq.GetDataValue(2, i))
                list_items.append(self.objRq.GetDataValue(3, i))
                list_items.append(self.objRq.GetDataValue(4, i))
                list_items.append(self.objRq.GetDataValue(5, i))
                list_items.append(self.objRq.GetDataValue(6, i))
                list_items.append(self.objRq.GetDataValue(7, i))
                list_items.append(self.objRq.GetDataValue(8, i))
                list_items.append(self.objRq.GetDataValue(9, i))
                list_items.append(self.objRq.GetDataValue(10, i))
                list_items.append(self.objRq.GetDataValue(11, i))
 
                list_jango_data.append(list_items)
            if (self.objRq.Continue == False):
                break

        return True


if __name__ == "__main__":
    if InitPlusCheck() == False:
        exit()
    obj6032 = Cp6032()    
    # 잔고 요청
    obj6032.request6032()

    if len(list_jango_data) == 0:
        print("No Jango Data!!!")
        exit()

    # 데이터 디비로 저장
    header = """
        INSERT INTO creon_earn
        ( JONGMOK_CD, DEAL_DT, JONGMOK_NM, PRE_JANGO, BUY_EA, BUY_EA, NOW_JANGO, AVG_BUY_PRC, AVG_SELL_PRC, PRC, REMAIN_EARN, SELL_EARN, EARN_RT )
        VALUES"""
    body = ""    
    # 디비로 저장
    for list_items in list_jango_data:
        body += f"""
            ('{list_items[0]}',
             '{DU.get_now_datetime_string()}',
             '{list_items[1]}',
              {list_items[2]},
              {list_items[3]},
              {list_items[4]},
              {list_items[5]},
              {list_items[6]},
              {list_items[7]},
              {list_items[8]},
              {list_items[9]},
              {list_items[10]},
              {list_items[11]},
              {list_items[12]}),
        """
    qry = header + "\n" + body[:len(body)-1]
    print(qry)
    
    DB.transaction_data(qry)
    