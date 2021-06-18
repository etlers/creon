import pandas as pd
import pymysql
from sqlalchemy import create_engine

pymysql.install_as_MySQLdb()
import MySQLdb

engine = create_engine("mysql+mysqldb://etlers:"+"wndyd"+"@localhost/stocks", encoding='utf-8')
conn = engine.connect()

jongmok_list_csv_file = 'C:/Users/etlers/Documents/project/CSV/jongmok_list.csv'

df_jongmok = pd.read_csv(jongmok_list_csv_file, encoding="CP949")
df_jongmok = df_jongmok[["단축코드", "한글 종목약명"]]
df_jongmok = df_jongmok.rename(columns = {'단축코드': 'JONGMOK_CD', '한글 종목약명': 'JONGMOK_NM'}, inplace = False)

df_jongmok.to_sql(name="jongmok_info", con=engine, if_exists='replace', index=False)
