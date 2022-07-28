import time
import os
import win32com.client
from pywinauto import application

# 설명: 커넥션 관리
# kill_client: 실행중인 크레온 HTS 프로그램을 종료합니다.
# connect: 크레온 ID, 비밀번호, 공인인증서 비밀번호를 입력받아서 크레온 HTS에 로그인 합니다.
# connected: 크레온 HTS에 연결되었는지 확인합니다.
# disconnect: 크레온 HTS와의 연결을 해제합니다.

class Creon:
    def __init__(self):
        self.obj_CpUtil_CpCybos = win32com.client.Dispatch('CpUtil.CpCybos')

    def kill_client(self):
        os.system('taskkill /IM coStarter* /F /T')
        os.system('taskkill /IM CpStart* /F /T')
        os.system('taskkill /IM DibServer* /F /T')
        os.system('wmic process where "name like \'%coStarter%\'" call terminate')
        os.system('wmic process where "name like \'%CpStart%\'" call terminate')
        os.system('wmic process where "name like \'%DibServer%\'" call terminate')

    def connect(self, id_, pwd, pwdcert):
        if not self.connected():
            self.disconnect()
            self.kill_client()
            app = application.Application()
            app.start(
                'C:\CREON\STARTER\coStarter.exe /prj:cp /id:{id} /pwd:{pwd} /pwdcert:{pwdcert} /autostart'.format(
                    id=id_, pwd=pwd, pwdcert=pwdcert
                )
            )
        while not self.connected():
            time.sleep(1)
        return True

    def connected(self):
        b_connected = self.obj_CpUtil_CpCybos.IsConnect
        if b_connected == 0:
            return False
        return True

    def disconnect(self):
        if self.connected():
            self.obj_CpUtil_CpCybos.PlusDisconnect()

    def order_strock(self, jongmok_cd, order_div, order_qty):

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
        objStockOrder.SetInputValue(0, order_div)   #  1: 매도, 2: 매수
        objStockOrder.SetInputValue(1, acc )   #  계좌번호
        objStockOrder.SetInputValue(2, accFlag[0])   #  상품구분 - 주식 상품 중 첫번째
        objStockOrder.SetInputValue(3, jongmok_cd)   #  종목코드 - A003540 - 대신증권 종목
        objStockOrder.SetInputValue(4, order_qty)   #  매도수량 10주
        objStockOrder.SetInputValue(5, 0)   #  주문단가  - 14,100원
        objStockOrder.SetInputValue(7, "0")   #  주문 조건 구분 코드, 0: 기본 1: IOC 2:FOK
        objStockOrder.SetInputValue(8, "03")   # 주문호가 구분코드 - 01: 보통 03:시장가 05:조건부지정가
        
        # 매도 주문 요청
        objStockOrder.BlockRequest()
        
        rqStatus = objStockOrder.GetDibStatus()
        rqRet = objStockOrder.GetDibMsg1()
        print("통신상태", rqStatus, rqRet)
        if rqStatus != 0:
            exit()


def execute():
    creon_process = Creon()
    # id, pwd, pwdcert
    creon_process.connect("","","")
    

if __name__ == "__main__":
    execute
