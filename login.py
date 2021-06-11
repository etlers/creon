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

if __name__ == "__main__":
    creon_process = Creon()
    creon_process.connect("","","")