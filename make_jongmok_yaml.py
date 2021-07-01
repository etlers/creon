import sys
import pandas as pd

sys.path.append("C:/Users/etlers/Documents/project/python/common")

import date_util as DU
import conn_db as DB

qry_head = """
INSERT INTO jongmok_info
(JONGMOK_CD, JONGMOK_NM, MARKET)
VALUES
"""

jongmok_csv_file = './csv/jongmok_list.csv'
jongmok_yaml_file = './config/jongmok.yaml'
yaml_file = open(jongmok_yaml_file, 'w', encoding="utf-8")

df_jongmok = pd.read_csv(jongmok_csv_file, encoding="cp949")
df_jongmok.rename(columns={"단축코드": "JONGMOK_CD", "한글 종목약명": "JONGMOK_NM", "시장구분": "MARKET"}, inplace=True)
df_jongmok = df_jongmok[["JONGMOK_CD","JONGMOK_NM","MARKET"]]

qry_body = ""
for key, row in df_jongmok.iterrows():
    yaml_file.write("A" + str(row["JONGMOK_CD"]) + ": " + row["JONGMOK_NM"] + "\n")
    qry_body += "('" + "A" + str(row["JONGMOK_CD"]) + "', '" + row["JONGMOK_NM"] + "', '" + row["MARKET"] + "')," + "\n"

# 데이터 초기화
qry = "TRUNCATE TABLE jongmok_info"
DB.transaction_data(qry)
# 저장 쿼리 생성
ins_qry = qry_head + qry_body[:len(qry_body)-2]

try:
    DB.transaction_data(ins_qry)
except Exception as e:
    print("Insert Jongmok Data Exception:", e)
    print("#"*100)
    print(ins_qry)
    print("#"*100)