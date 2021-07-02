"""
    기업 종목 분석
"""
import requests
from bs4 import BeautifulSoup as bs

def make_analysis_jongmok():

    def get_detail(base_url):
        response = requests.get( base_url, headers={"User-agent": "Mozilla/5.0"} )
        soup = bs(response.text, 'html.parser')
        idx = 0

        idx = 0
        list_content = str(soup.find("div", {"class":"articleCont"})).split("\n")
        idx = 0
        for contents in list_content:
            content = contents.strip()
            idx += 1
            if idx != 2: continue
            desc = content.split("</span>")[1].replace("<br/>"," ").replace("<br>"," ").replace("</br>"," ").split("<span")[0]
            if "</h3>" in desc: continue
            desc = desc.split("<div")[0].split("<!--")[0].replace('"',"'")
            if len(desc) < 20: continue
            print(desc.strip())

    
    def make_page_num(dt):
        list_pg = []
        base_url = f"https://finance.naver.com/news/news_list.nhn?mode=LSS3D&section_id=101&section_id2=258&section_id3=402&date={dt}"
        response = requests.get( base_url, headers={"User-agent": "Mozilla/5.0"} )
        soup = bs(response.text, 'html.parser')

        list_pgnum = str(soup.find("table",{"summary":"페이지 네비게이션 리스트"})).split("\n")
        for num in list_pgnum:
            if "href" in num:
                try:
                    pg = int(num.split(">")[1].split("<")[0])
                except:
                    continue
                list_pg.append(pg)

        return list_pg

    list_dt = ["20210702", "20210701"]
    
    for dt in list_dt:
        list_pg = make_page_num(dt)
        for page in list_pg:
            print(dt, page)
            base_url = f"https://finance.naver.com/news/news_list.nhn?mode=LSS3D&section_id=101&section_id2=258&section_id3=402&date={dt}&page={page}"
            response = requests.get( base_url, headers={"User-agent": "Mozilla/5.0"} )
            soup = bs(response.text, 'html.parser')
            idx = 0

            idx = 0
            list_hedline = str(soup.find("div",id="contentarea_left")).split("\n")
            for row in list_hedline:
                headline = row.strip()
                if ("href" in headline and "title" in headline):
                    href_title = headline.split("<a href=")[1]
                    href = "https://finance.naver.com" + href_title.split("title=")[0].replace("amp;","").replace('"','').replace("§ion","&section")
                    title = href_title.split("title=")[1].replace("</a>","").split('">')[0].replace('"',' ').strip().replace("</span>","")
                    get_detail(href)


make_analysis_jongmok()