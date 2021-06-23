import yaml
import requests
from bs4 import BeautifulSoup as bs

quant_high_yaml_file = './config/quant_high.yaml'

# 환경변수 추출
with open(quant_high_yaml_file) as stream:
    try:
        dict_quant = yaml.safe_load(stream)
        url_param = dict_quant['url_param']
    except yaml.YAMLError as exc:
        print(exc)

# 뉴스 속보
def get_quick_news():
    list_quick_news = []
    # 4 페이지 데이터
    for page in range(4):
        if page == 0:
            base_url = url_param["quick_news"]
        else:
            base_url = url_param["quick_news"] + f"&page={page+1}"
        response = requests.get( base_url )
        response
        
        soup = bs(response.text, 'html.parser')

        content = soup.select("div.hotNewsList")
        list_content = str(content).split("\n")
        
        for str_content in list_content:
            if "href" in str_content:
                try:
                    head_line = str_content.split('title=')[1]
                except:
                    head_line = str_content

                list_quick_news.append(head_line[1:].replace("&quot;","").replace("</a>","").replace("&amp;","&").split('">')[0])

    return list_quick_news