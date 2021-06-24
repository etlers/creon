from os import remove
import requests
from bs4 import BeautifulSoup as bs
import time, sys, yaml

sys.path.append("C:/Users/etlers/Documents/project/python/common")

import date_util as DU
import conn_db as DB

# 파일 경로
result_txt_file = './txt/naver_condition_deal.txt'
quant_high_yaml_file = './config/quant_high.yaml'
# 주문내역 저장할 텍스르 파일
txt_file = open(result_txt_file, 'w', encoding="utf-8")

# 환경변수 추출
with open(quant_high_yaml_file) as stream:
    try:
        dict_quant = yaml.safe_load(stream)
        url_param = dict_quant['url_param']
        query_param = dict_quant['query_param']
        hms_param = dict_quant['hms_param']
    except yaml.YAMLError as exc:
        print(exc)

# 골든크로스. 단기(20일) 이동평균선이 장기(60일) 이동평균선을 돌파하는 경우의 종
url_gold = "https://finance.naver.com/sise/item_gold.nhn"
# 갭상승. 갭상승 종목중에서 전일 고가보다 당일 저가가 높은 종
url_gap = "https://finance.naver.com/sise/item_gap.nhn"
# 이격도과열. 당일 주가(현재가)를 이동평균값(20일)으로 나눈 비율이 120%이상 일 경우의 종목
url_igyuk = "https://finance.naver.com/sise/item_igyuk.nhn"
# 상대강도과열. 14일의 상승폭 합/(14 일의 상승폭 합+하락폭 합)의 비율이며 그 비율이 80%이상 일 경우의 종목
url_overheat = "https://finance.naver.com/sise/item_overheating_2.nhn"
# 데이터 추출 URL
list_condition = [
    url_igyuk, url_overheat, url_gap, url_gold
]
list_quant_high_url = [
    url_param["sise_quant_high"]["kospi"],
    url_param["sise_quant_high"]["kosdak"]
]
list_low_up_url = [
    url_param["sise_low_up"]["kospi"],
    url_param["sise_low_up"]["kosdak"]
]
list_sise_url = [
    url_param["sise_rising"]["kospi"],
    url_param["sise_rising"]["kosdak"]
]

qry_head = """
INSERT INTO naver_condition_simul
(INS_DTM, JONGMOK_CD, JONGMOK_NM, PRC, UP_RT, VOL, RNK, POINTS)
VALUES
"""


# 랭킹에 따른 포인트
def calc_rank_point(rnk):
    if rnk < 4: points = 10
    elif rnk < 10: points = 7
    elif rnk < 21: points = 5
    elif rnk < 31: points = 3
    else: points = 1
    
    return points

# 데이터 타입에 맞게 재생성
def remake_list(list_base, num_cols, rate_cols):    
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

# 급등 데이터 추출
def get_sudden_rising_data(base_url):
    list_whole = []

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

    return list_whole

# 급등 데이터 생성
def get_sudden_rising(ins_dtm):

    def make_qry_n_save_data(list_result, list_data_value):     
        body = ""
        rnk = 0
        for list_row in list_result:
            row = "( '" + ins_dtm + "', "
            rnk += 1
            for idx in range(len(list_row)):
                if idx in list_data_value:
                    try:
                        row += "'" + list_row[idx] + "', "
                    except:
                        row += str(list_row[idx]) + ", "
            # 포인트 계산
            points = calc_rank_point(rnk)
            row += str(rnk) + ", " + str(points) + ")," + "\n"
            row = row.replace(", )", ")")
            body += row
        # 저장 쿼리 생성
        ins_qry = qry_head + body
        ins_qry = ins_qry[:len(ins_qry)-2]
        # 디비로 저장
        try:
            DB.transaction_data(ins_qry)
        except Exception as e:
            print("Insert Naver Data Exception:", e)
            print("#"*100)
            print(ins_qry)
            print("#"*100)

    def save_low_up_data():
        num_cols = [3,4,6,7,8,9]
        rate_cols = [0,5,10,11]
        # 등록일시
        ins_dtm = DU.get_now_datetime_string()
        # 코스닥, 코스피 데이터 생성
        for url in list_low_up_url:
            list_whole = get_sudden_rising_data(url)
            
            list_result = []
            for list_row in list_whole:
                if len(list_row) == 12:
                    list_result.append(remake_list(list_row, num_cols, rate_cols))
            list_data_value = [1, 2, 3, 5, 9]
                    
            make_qry_n_save_data(list_result, list_data_value)

    def save_quant_high_data():
        num_cols = [3,4,6,7,8,9]
        rate_cols = [0,5,10]
        # 등록일시
        ins_dtm = DU.get_now_datetime_string()
        # 코스닥, 코스피 데이터 생성
        for url in list_quant_high_url:
            list_whole = get_sudden_rising_data(url)
            
            list_result = []
            for list_row in list_whole:
                if len(list_row) == 11:
                    list_result.append(remake_list(list_row, num_cols, rate_cols))
            list_data_value = [1, 2, 3, 5, 8]
                    
            make_qry_n_save_data(list_result, list_data_value)

    def save_sise_rising():
        num_cols = [2,3,5,6,7,8,9]
        rate_cols = [4,10,11]
        # 등록일시
        ins_dtm = DU.get_now_datetime_string()
        # 코스닥, 코스피 데이터 생성
        for url in list_sise_url:
            list_whole = get_sudden_rising_data(url)
            
            list_result = []
            for list_row in list_whole:
                if len(list_row) == 12:
                    list_result.append(remake_list(list_row, num_cols, rate_cols))
            list_data_value = [0, 1, 2, 4, 5]
                    
            make_qry_n_save_data(list_result, list_data_value)

    # 저가대비 급등
    save_low_up_data()
    # 거래량 급증
    save_quant_high_data()
    # 시세 급등
    save_sise_rising()

def get_condition_data(base_url):
    list_whole = []

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

    return list_whole

def execute(base_url, ins_dtm):
    list_gold = get_condition_data(base_url)
    rnk = 0
    qry_body = ""
    for list_row in list_gold:
        if len(list_row) != 11: continue
        rnk += 1
        # 포인트 계산
        points = calc_rank_point(rnk)
        qry_body += "('" + ins_dtm + "', '"+ list_row[0] + "', '" + list_row[1] + "', " + list_row[2].replace(",","") + ", " + list_row[4].replace(",","").replace("%","").replace("+","") + ", " + list_row[5].replace(",","") + ", " + str(rnk) + ", " + str(points) + "),"
    ins_qry = qry_head + qry_body
    ins_qry = ins_qry[:len(ins_qry)-1]
    
    # 디비로 저장
    try:
        DB.transaction_data(ins_qry)
    except Exception as e:
        print("Insert Naver Data Exception:", e)
        print("#"*100)
        print(ins_qry)
        print("#"*100)        
    

if __name__ == "__main__":

    # 데이터 초기화
    qry = "TRUNCATE TABLE naver_condition_simul"
    DB.transaction_data(qry)

    pre_hm = ""

    while True:
        now_tm = DU.get_now_datetime_string().split(" ")[1].replace(":","")
        # 9시 3분부터 30분까지만 데이터 적재
        if now_tm < "090300":
            print("시작대기: ", DU.get_now_datetime_string())
            time.sleep(1)
            continue
        elif now_tm > "093000":
            break
        # 1분마다 적재
        ins_dtm = DU.get_now_datetime_string()
        if pre_hm != now_tm[:4]:
            for url in list_condition:
                execute(url, ins_dtm)
            # 급등주 추출 & 저장
            get_sudden_rising(ins_dtm)

        time.sleep(1)
        print("추출대기: ", DU.get_now_datetime_string())
        pre_hm = now_tm[:4]