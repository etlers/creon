"""
    장 요약 데이터
"""
import requests
from bs4 import BeautifulSoup as bs
import sys

sys.path.append("C:/Users/etlers/Documents/project/python/common")

import date_util as DU
import conn_db as DB

base_url = f"https://finance.naver.com/"
response = requests.get( base_url, headers={"User-agent": "Mozilla/5.0"} )
soup = bs(response.text, 'html.parser')

dict_market = {
    1: "KOSPI", 2: "KOSDAQ", 3: "KOSPI200"
}

list_num = [
    4, 17, 24, 31,
]

def remove_char(row):
    tmp_string = row.strip()
    if '상세보기' in tmp_string:
        split_val = tmp_string.split('상세보기">')[1]
        jisu = split_val.split('</span>')[0].split('">')[2]
        updown = split_val.split('</span>')[1].split('">')[1]
        sign = split_val.split('</span>')[2].split('">')[2]
        if sign == "-":
            sign = -1
        else:
            sign = 1
        rt = split_val.split('</span>')[3].split('<')[0]
        return jisu, updown, sign, rt
    else:
        try:
            return row.split(';">')[1].replace("</a>","")
        except:
            return row.strip()

def execute():
    list_jisu = []
    for row in soup.find("div",{"class":"section_stock"}):
        list_row = str(row).split("\n")
        idx = 0
        list_temp = []
        for line in list_row:
            idx += 1
            if idx not in list_num: continue

            if idx == 4:
                jisu, updown, sign, rt = remove_char(line)
                list_temp.append("'" + DU.get_now_datetime_string() + "'")
                list_temp.append(jisu)
                list_temp.append(updown)
                list_temp.append(sign)
                list_temp.append(rt)
            else:
                list_temp.append(remove_char(line))
        if len(list_temp) > 0:
            list_jisu.append(list_temp)
            list_temp = []

    idx = 0
    list_line = []
    head = """
    INSERT INTO jang_yoyak
    VALUES
    """
    body = ""
    for list_row in list_jisu:
        idx += 1
        line = "('" + dict_market[idx] + "', "
        for row in list_row:
            try:
                line += row.replace(",","").replace("+","") + ", "
            except:
                line += str(row) + ", "
        body += line[:len(line)-2] + ")," + "\n"

    # 데이터 초기화
    # qry = "TRUNCATE TABLE jang_yoyak"
    # DB.transaction_data(qry)
    # 요약 데이터 저장
    ins_qry = head + body[:len(body)-2]
    try:
        DB.transaction_data(ins_qry)
    except Exception as e:
        print("Insert Jang Yoyak Data Exception:", e)
        print("#"*100)
        print(ins_qry)
        print("#"*100)


if __name__ == "__main__":
    execute()