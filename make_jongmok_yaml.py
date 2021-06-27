import pandas as pd

jongmok_csv_file = './csv/jongmok_list.csv'
jongmok_yaml_file = './config/jongmok.yaml'
yaml_file = open(jongmok_yaml_file, 'w', encoding="utf-8")

df_jongmok = pd.read_csv(jongmok_csv_file, encoding="cp949")
df_jongmok.rename(columns={"단축코드": "JONGMOK_CD", "한글 종목약명": "JONGMOK_NM"}, inplace=True)
df_jongmok = df_jongmok[["JONGMOK_CD","JONGMOK_NM"]]

for key, row in df_jongmok.iterrows():
    yaml_file.write("A" + str(row["JONGMOK_CD"]) + ": " + row["JONGMOK_NM"] + "\n")