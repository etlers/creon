import requests
from bs4 import BeautifulSoup as bs
import time, sys, yaml
import win32com.client
import quick_news as NEWS
import creon as CREON

sys.path.append("C:/Users/etlers/Documents/project/python/common")

import date_util as DU
import conn_db as DB


# 파일 경로
result_txt_file = './txt/naver_deal.txt'
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
# 기본 금액
base_amount = dict_quant["base_amount"]
# 잔고 조회를 위한 종목
list_jongmok_cd = []
# 데이터 추출 URL
kospi_url = "https://finance.naver.com/sise/sise_low_up.nhn?sosok=0"
kosdak_url = "https://finance.naver.com/sise/sise_low_up.nhn?sosok=1"
list_url = [
    kospi_url, kosdak_url
]
# 매수를 위한 추출 쿼리
extract_qry = f"""
SELECT JONGMOK_CD, JONGMOK_NM
     , PRC
     , GAP_PRC_RT
     , GAP_VOL_RT
     , GAP_LOW_VS_RT
  FROM (SELECT JONGMOK_CD, JONGMOK_NM
             , PRC, PRE_PRC
             , ROUND(((PRC - PRE_PRC) / PRE_PRC) * 100 , 2) AS GAP_PRC_RT
			 , VOL, PRE_VOL
			 , VOL - PRE_VOL AS GAP_VOL
			 , ROUND(((VOL - PRE_VOL) / PRE_VOL) * 100 , 2) AS GAP_VOL_RT
			 , LOW_VS_RT, PRE_LOW_VS_RT
			 , ROUND(LOW_VS_RT - PRE_LOW_VS_RT, 2) AS GAP_LOW_VS_RT
		  FROM (SELECT *
				     , LAG(PRC, 3) OVER(PARTITION BY JONGMOK_CD ORDER BY INS_DTM) AS PRE_PRC
				     , LAG(VOL, 3) OVER(PARTITION BY JONGMOK_CD ORDER BY INS_DTM) AS PRE_VOL
				     , LAG(LOW_VS_RT, 3) OVER(PARTITION BY JONGMOK_CD ORDER BY INS_DTM) AS PRE_LOW_VS_RT
				  FROM naver_low_vs_rt
				 WHERE 1 = 1
                   AND LOW_VS_RT > 5.0
				   AND VOL > 1000000
				   AND PRC BETWEEN 5000 AND 25000
				   AND ROE > 0.0
				 ORDER BY JONGMOK_CD, INS_DTM DESC) T1
		 WHERE 1 = 1
		   AND INS_DTM = (SELECT MAX(INS_DTM) FROM naver_low_vs_rt)) TT
 WHERE 1 = 1
   AND GAP_LOW_VS_RT >= 3.0
   AND GAP_PRC_RT >= 1.0
   AND GAP_VOL_RT >= 10.0   
 ORDER BY GAP_LOW_VS_RT DESC, GAP_PRC_RT DESC, GAP_VOL_RT DESC   
 LIMIT 3
"""


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
                # header
                if i == 1:
                    print("종목코드 종목명 신용구분 체결잔고수량 체결장부단가 평가금액 평가손익")
                # Data
                print(code, name, cashFlag, amount, buyPrice, evalValue, evalPerc)
                # 수익률 10원 단위로 매도하기 위한 설정
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


# 데이터 타입에 맞게 재생성
def remake_list(list_base):
    num_cols = [3,4,6,7,8,9]
    rate_cols = [0,5,10,11]
    for idx in range(len(num_cols)):
        try:
            num = int(list_base[num_cols[idx]].replace(",",""))
        except:
            num = 0
        list_base[num_cols[idx]] = num
    for idx in range(len(rate_cols)):
        try:
            num = float(list_base[rate_cols[idx]].replace(",","").replace("%",""))
        except:
            num = 0
        list_base[rate_cols[idx]] = num
        
    return list_base


list_whole = []
# 저가대비 급등 데이터 저장
def get_sudden_rising_data(base_url):
    response = requests.get( base_url )
    soup = bs(response.text, 'html.parser')

    content = soup.select("div.box_type_l")
    list_content = str(content).split("\n")
    list_jongmok = []
    for row_data in list_content:
        row = row_data.strip().replace("\t","")
        if '<td class="no">' in row:
            if len(list_jongmok) > 0:
                list_whole.append(list_jongmok)
                list_jongmok = []
        elif "tltle" in row:
            jongmok_cd = row.split("code=")[1].split('"')[0]
            jongmok_nm = row.split("code=")[1].split('"')[1].split('</a')[0].replace(">","")
            list_jongmok.append("A" + jongmok_cd)
            list_jongmok.append(jongmok_nm)
        elif row[:1] != "<":
            list_jongmok.append(row)
        elif ("<td" not in row or row[:4] == "<tr>"):
            continue
        else:
            num_val = row.replace('<td class="number">','')
            if len(num_val) == 0:
                continue
            list_jongmok.append(num_val.replace("</td>",""))


# 저가대비 급등 데이터 생성
def make_sudden_rising():
    # 코스닥, 코스피 데이터 생성
    for url in list_url:
        get_sudden_rising_data(url)
        
    list_result = []
    for list_row in list_whole:
        if len(list_row) == 12:
            list_result.append(remake_list(list_row))
            
    head = """
    insert into naver_low_vs_rt
    (INS_DTM, LOW_VS_RT, JONGMOK_CD, JONGMOK_NM, PRC, PRE_VS_GAP, PRE_VS_RT, START_PRC, HIGH_PRC, LOW_PRC, VOL, PER, ROE)
    values
    """
    body = ""
    for list_row in list_result:
        row = "( '" + DU.get_now_datetime_string() + "', "
        for idx in range(len(list_row)):
            try:
                row += "'" + list_row[idx] + "', "
            except:
                row += str(list_row[idx]) + ", "
        row += ")," + "\n"
        row = row.replace(", )", ")")
        body += row
    # 저장 쿼리 생성
    ins_qry = head + body
    ins_qry = ins_qry[:len(ins_qry)-2]
    # 디비로 저장
    DB.transaction_data(ins_qry)


# 구매한 금액, 수량
def get_buy_price():
    remain = Cp6033()
    remain.Request(list_jongmok_cd)


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
# 매수 매도를 위한 종목 코드
dict_sell_info = {}


# 매수, 매도
def order_stock(jongmok_cd, div, qty, prc, ho_div, jongmok_nm=""):
    result_tf = False
    print("#" * 50)
    print("#주문:", jongmok_cd, dict_order_div[div], qty, prc, dict_ho_div[ho_div])    
    print("#" * 50)
    # 파일 생성 시에 오류로 종료되면 안되기에 예외처리
    try:
        txt_file.write("# 주문: " + dict_order_div[div])
        txt_file.write("  - " + "\t" + jongmok_cd + " [" + jongmok_nm + "]" + "\t" + format(qty, ",") + "\t" + format(prc, ",") + "\t" + dict_ho_div[ho_div] + "\n")
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


# 종목 추출 & 매수, 매도 처리
def order_buy(jongmok_cd, jongmok_nm, now_price):    
    base_price = int((now_price * 1.3) / 10) * 10
    # 계산한 매수량
    buy_ea = int(base_amount / base_price)
    # 한 종목에 최대 100주
    if buy_ea > 100:
        buy_ea = 100
    # 시장가 매수
    if order_stock(jongmok_cd, "2", buy_ea, 0, "03", jongmok_nm):
        return True
    else:
        return False
    

if __name__ == "__main__":

    # 시간 내에 매도를 못 했다면 시가 정리매도 진행
    def sell_all_stokcs():
        # 잔고 요청
        get_buy_price()
        # 보유한 주식 매도
        for key, list_val in dict_sell_info.items():
            if list_val[0] == 0: continue
            try:
                # 시장가 매도
                order_stock(key, "1", list_val[0], 0, "03")
            except Exception as e:
                print("sell_all_stokcs Exception:", e)

    # 데이터 초기화
    qry = "TRUNCATE TABLE naver_low_vs_rt"
    DB.transaction_data(qry)
    ################################################################################################
    # 매수하는 로직
    ################################################################################################
    while True:
        now_tm = DU.get_now_datetime_string().split(" ")[1].replace(":","")
        # 9시부터 10초 후에 최초 데이터 저장. 30분 동안만 처리
        if now_tm < "090030":
            print(now_tm)
            time.sleep(1)
            continue
        # 종료시간 확인
        elif now_tm > end_hms:
            break
        # 매수작업
        else:
            # 저가대비 급등 주 데이터 추출
            make_sudden_rising()
            # 매수 조건에 맞는 데이터 추출
            list_rising = DB.query_data(extract_qry)
            # 존재하면 매수
            if len(list_rising) > 0:
                # 매수 주문
                for row in list_rising:
                    jongmok_cd = row[0]
                    jongmok_nm = row[1]
                    now_price = row[2]
                    order_buy(jongmok_cd, jongmok_nm, now_price)
                break
    ################################################################################################

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
    # 지정가에 매도를 못한 경우 시장가 매도를 위한 대기
    while True:
        now_tm = DU.get_now_datetime_string().split(" ")[1].replace(":","")
        # 적재 지정시간과 잔고 정리 시간이 지나면 종료
        if now_tm > clear_hms:
            break
        else:
            print("잔고정리 대기 중...", now_tm)
        # 1분 단위로
        time.sleep(60)

    # 미체결 리스트를 보관한 자료 구조체
    diOrderList= dict()  # 미체결 내역 딕셔너리 - key: 주문번호, value - 미체결 레코드
    orderList = []       # 미체결 내역 리스트 - 순차 조회 등을 위한 미체결 리스트
    # 미체결 통신 object
    obj = CREON.Cp5339()
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
    objOrder = CREON.CpRPOrder()
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