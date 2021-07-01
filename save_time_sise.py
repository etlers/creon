"""
    분단위 거래내역
"""
import requests
from bs4 import BeautifulSoup as bs
import sys

sys.path.append("C:/Users/etlers/Documents/project/python/common")

import date_util as DU
import conn_db as DB


def save_data(cd, up_cnt, inc_cnt):
    qry = f"""
        INSERT INTO time_sise
            (JONGMOK_CD, UP_CNT, INC_CNT) 
        VALUES
            ('A{cd}', {up_cnt}, {inc_cnt})
        ON DUPLICATE KEY
        UPDATE 
            UP_CNT = {up_cnt}
          , INC_CNT = {inc_cnt}
    """
    try:
        DB.transaction_data(qry)
    except Exception as e:
        print("Insert Time Sise Data Exception:", e)
        print("#"*100)
        print(qry)
        print("#"*100)

def make_data(cd):
    now_dt = DU.get_now_datetime_string().split(" ")[0].replace("-","")
    now_hm = DU.get_now_datetime_string().split(" ")[1].replace(":","")[:4]
    # 항상 가장 최근 10개만 가져옴
    base_url = f"https://finance.naver.com//item/sise_time.nhn?code={cd}&thistime={now_dt}{now_hm}59&page=1"
    response = requests.get( base_url, headers={"User-agent": "Mozilla/5.0"} )
    soup = bs(response.text, 'html.parser')

    list_num = [
        2, 5, 6,
    ]

    cnt = 0
    list_sise = []
    list_hm = []
    for row in soup.find("table",{"class":"type2"}):
        list_row = str(row).split("\n")
        idx = 0
        for line in list_row:
            strip_line = line.strip()
            if len(strip_line) == 0: continue
            idx += 1
            if idx in list_num:
                try:
                    if idx == 5:
                        if "nv01" in strip_line:
                            strip_line = -1
                        else:
                            strip_line = 1
                    elif idx == 6:
                        try:
                            strip_line = int(strip_line.replace(",",""))
                        except:
                            continue
                    else:
                        strip_line = strip_line.split('">')[2].replace('</span></td>','').replace(",","")     
                    list_hm.append(strip_line)           
                except:
                    pass
        if len(list_hm) > 1:
            if len(list_hm) == 2:
                list_hm.append(0)
            list_hm.append(list_hm[1] * list_hm[2])
            list_sise.append(list_hm)
        list_hm = []
    
    # 연속 증가
    inc_cnt = 0
    max_inc_cnt = 0
    # 전일대비 증가
    up_cnt = 0
    for idx in range(len(list_sise)-1, 0, -1):
        now_gap = list_sise[idx][3]
        pre_gap = list_sise[idx-1][3]
        if now_gap < 1: continue
        up_cnt += 1
        if now_gap > pre_gap:
            inc_cnt += 1
        else:
            if inc_cnt > max_inc_cnt:
                max_inc_cnt = inc_cnt
            inc_cnt = 0
    try:
        if list_sise[9][3] > 0:
            up_cnt += 1
    except:
        pass

    save_data(cd, up_cnt, max_inc_cnt)

def execute():
    # 데이터 초기화
    qry = "TRUNCATE TABLE time_sise"
    DB.transaction_data(qry)

    extract_qry = f"""
        SELECT DISTINCT JONGMOK_CD
          FROM naver_news
         WHERE 1 = 1
           AND NEG_CNT = 0
           AND POS_CNT - NEG_CNT > 0
    """
    list_jongmok = DB.query_data(extract_qry)
    for jongmok in list_jongmok:
        make_data(jongmok[0].replace("A",""))

    print(DU.get_now_datetime_string(), "시세정보 생성 완료")


if __name__ == "__main__":
    # '293490'
    execute()