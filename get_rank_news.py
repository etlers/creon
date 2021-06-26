import requests
from bs4 import BeautifulSoup as bs
import pandas as pd
import sys

sys.path.append("C:/Users/etlers/Documents/project/python/common")

import date_util as DU
import conn_db as DB

jongmok_list_csv_file = 'C:/Users/etlers/Documents/project/CSV/jongmok_list.csv'

qry_head = """
INSERT INTO naver_news
(JONGMOK_CD, JONGMOK_NM, POS_CNT, NEG_CNT, END_PRC, END_PRC_INC, HIGH_RT, HIGH_PRC, LOW_PRC, LOW_GAP, VOL)
VALUES
"""

list_url = []
def make_get_url():
    idx = DU.get_now_datetime().weekday()
    list_date = []
    # 당일은 기본 포함
    list_date.append(DU.get_before_datetime(DU.get_now_datetime_string()).split(" ")[0])
    # 월요일이면 토, 일
    if idx == 1:
        for day in range(2):
            list_date.append(DU.get_before_datetime(DU.get_now_datetime_string(), days=day+1).split(" ")[0])
    # 토요일 이전이면 이전 요일만
    else:
        list_date.append(DU.get_before_datetime(DU.get_now_datetime_string(), days=1).split(" ")[0])
    
    for date in list_date:
        for page in range(10):
            list_url.append(f"https://finance.naver.com/news/news_list.nhn?mode=RANK&date={date}&page={page+1}")

def make_jongmok_dict():
    dict_jongmok_nm = {}
    df_jongmok = pd.read_csv(jongmok_list_csv_file, encoding="CP949")
    # DataFrame에서 딕셔너리 생성
    try:
        df_jongmok = df_jongmok[["단축코드", "한글 종목약명"]]
        for index, row in df_jongmok.iterrows():
            dict_jongmok_nm["A" + row["단축코드"]] = row["한글 종목약명"]
    except:
        pass
    
    return dict_jongmok_nm


def remove_char(in_str):
    result_str = in_str.split(">")[2].replace('</span',"").replace(",","")
    
    return result_str


# 최근 10일간의 고가, 저가, 거래량(평균)
def get_prc_vol(cd):
    base_url = f"https://finance.naver.com/item/sise_day.nhn?code={cd}"
    response = requests.get( base_url, headers={"User-agent": "Mozilla/5.0"} )
    soup = bs(response.text, 'html.parser')
    
    gap = 5

    list_end_prc = []
    end_prc_high = 0
    high_prc = 0
    low_prc = 9999999
    vol = 0

    idx = 0
    for href in soup.find("table",{"class":"type2"}).find_all("td"):
        num_val = str(href).replace("\n","")
        if ('<img alt' in num_val or '<td bgcolor' in num_val or '<td colspan="7" height="8"></td>' in num_val): continue
        if '>0</span></td>' in num_val: continue
        if '<td class="num">' not in num_val: continue
        idx += 1
        # 종가
        if idx % gap == 1:
            list_end_prc.append(int(remove_char(num_val)))
            if int(remove_char(num_val)) > end_prc_high:
                end_prc_high = int(remove_char(num_val))
        # 고가
        elif idx % gap == 3:
            try:
                if int(remove_char(num_val)) > high_prc:
                    high_prc = int(remove_char(num_val))
            except:
                high_prc = 0
        # 저가
        elif idx % gap == 4:
            try:
                if int(remove_char(num_val)) < low_prc:
                    low_prc = int(remove_char(num_val))
            except:
                low_prc = 9999999
        # 5의 배수면 거래량
        elif idx % gap == 0:
            try:
                vol += int(remove_char(num_val))
            except:
                vol += 0

    inc_cnt = 0
    max_inc_cnt = 0
    try:
        for idx in range(9, 1, -1):
            if list_end_prc[idx] > list_end_prc[idx-1]:
                inc_cnt += 1
            else:
                if inc_cnt > max_inc_cnt:
                    max_inc_cnt = inc_cnt
                inc_cnt = 0
    except:
        pass

    max_inc_cnt
    return end_prc_high, high_prc, low_prc, int(vol / 10), max_inc_cnt


list_pos = [
    "부각","저평가","추천","매력","실적개선","러브콜","수익성개선","수익증대","실적지속","훨훨","강세","자금몰려","강력매수","계약체결","급등세","사업공급",
    "목표가↑","기대감↑","수혜","연속상한가","뚫었다","수주확대","단독공급","사용승인","사용허가","사업진출","특허취득","MOA체결","비중확대","호실적","회복",
    "허가획득","최초","상수상","특허출원","매수몰려","특허취득","우선협상대상자","상승인"
]
list_neg = [
    "그랬을까","고평가","하락","보류","손실증가","부진","미끄럼","저하","우려","약세","?","와르르","하향","없어","약세","가능성확인","부담","악화",
    "사유추가발생","정지"
]
def get_pos_neg_cnt(row):
    pos_cnt = 0
    neg_cnt = 0
    
    article = row.replace(" ","")
    for pos in list_pos:        
        if pos in article: pos_cnt += 1
    for neg in list_neg:
        if neg in article: neg_cnt += 1
                
    return pos_cnt, neg_cnt


def match_full_name(row, nm):
    row = row.replace('"','').replace(","," ").replace("…"," ").replace("...", " ").replace("·"," ")
    list_row = row.split(" ")
    for val in list_row:
        if nm == val:
            return True
    return False

list_result = []
def get_news(base_url):
    response = requests.get( base_url )
    response
    
    soup = bs(response.text, 'html.parser')

    content = soup.select("div.hotNewsList")
    list_content = str(content).split("\n")

    list_day_news = []
    for str_content in list_content:
        if "href" in str_content:
            try:
                head_line = str_content.split('title=')[1]
            except:
                head_line = str_content

            list_day_news.append(head_line[1:].replace("&quot;","").replace("</a>","").replace("&amp;","&").split('">')[0])

    list_result.append(list(set(list_day_news)))

def execute():
    make_get_url()
    for url in list_url:
        get_news(url.replace("-",""))

    dict_jongmok_nm = make_jongmok_dict()
    list_whole = []
    for cd, nm in dict_jongmok_nm.items():
        for list_row in list_result:
            for headline in list_row:
                if nm in headline:
                    if match_full_name(headline, nm):
                        list_select = []
                        list_select.append(cd)
                        list_select.append(nm)
                        list_select.append(headline.replace("]","").replace("[",""))
                        pos_cnt, neg_cnt = get_pos_neg_cnt(headline)
                        list_select.append(pos_cnt)
                        list_select.append(neg_cnt)
                        end_prc_high, high_prc, low_prc, avg_vol, max_inc_cnt = get_prc_vol(cd.replace("A",""))
                        list_select.append(end_prc_high)
                        list_select.append(max_inc_cnt)
                        high_rt = round((high_prc - end_prc_high) / end_prc_high * 100, 2)
                        high_rt = 100.00 - high_rt
                        list_select.append(high_rt)
                        list_select.append(high_prc)
                        list_select.append(low_prc)
                        gap_75 = int(int((high_prc - low_prc) * 0.85 + low_prc) / 10) * 10
                        list_select.append(gap_75)
                        list_select.append(avg_vol)
                        list_whole.append(list_select)

    list_cols = ["종목코드", "종목명", "기사", "긍정", "부정", "종가", "종가연속증가", "종가비율", "고가", "저가", "85%", "거래량"]
    df_news = pd.DataFrame(list_whole, columns=list_cols)
    df_news = df_news.drop_duplicates()
    df_news.to_csv("news.csv", index=False, encoding="utf-8-sig")
    # df_news = df_news[(df_news.긍정 > df_news.부정) & (df_news.종가 < 100000) & (df_news.거래량 > 500000)]
    # df_news = df_news.sort_values(by=["긍정"], ascending=False)
    
    qry_body = ""
    for key, row in df_news.iterrows():
        qry_body += "('" + row["종목코드"] + "','" + row["종목명"] + "'," + str(row["긍정"]) + "," + str(row["부정"]) + "," + str(row["종가"]) \
                         + "," + str(row["종가연속증가"]) + "," + str(row["종가비율"]) + "," + str(row["고가"]) + "," + str(row["저가"]) \
                         + "," + str(row["85%"]) + "," + str(row["거래량"]) + ")," + "\n"
    
    # 데이터 초기화
    qry = "TRUNCATE TABLE naver_news"
    DB.transaction_data(qry)
    # 저장 쿼리 생성
    ins_qry = qry_head + qry_body
    ins_qry = ins_qry[:len(ins_qry)-2]
    # 디비로 저장
    try:
        DB.transaction_data(ins_qry)
    except Exception as e:
        print("Insert Naver News Data Exception:", e)
        print("#"*100)
        print(ins_qry)
        print("#"*100)


if __name__ == "__main__":
    execute()