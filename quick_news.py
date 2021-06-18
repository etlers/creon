import requests
from bs4 import BeautifulSoup as bs

# 뉴스 속보
def get_quick_news():
    list_quick_news = []
    # 4 페이지 데이터
    for page in range(4):
        if page == 0:
            base_url = f"https://finance.naver.com/news/news_list.nhn?mode=RANK"
        else:
            base_url = f"https://finance.naver.com/news/news_list.nhn?mode=RANK&page={page+1}"
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