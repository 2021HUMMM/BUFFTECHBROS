from django.conf import settings
from django.shortcuts import render
import requests
from newspaper import Article

def show_news(request):
    news_data = get_news("bitcoin")  # you can change this to dynamic input
    combined_news = combine_news(news_data)  # combine all articles into one string
    context = {
        'news_data': news_data,  # this is a list of article dictionaries
        'combined_news': combined_news,  # this is the combined text of all articles
    }
    return render(request, 'news.html', context)

def get_news(topic):
    url = "https://newsdata.io/api/1/latest"
    params = {
        "apikey": settings.NEWS_API_KEY_2,
        "q": topic,
        "language": "id",  # optional, can also use 'id' for Indonesian
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()  # raise error for bad response (4xx/5xx)
        data = response.json()
        return data.get("results", [])  # safely get list of articles
    except requests.exceptions.RequestException as e:
        print("NewsData API Error:", e)
        return []
    
def combine_news(data):
    combined_news = ""
    if data:
        for article in data:
            try:
                url = article["link"]
                article = Article(url)
                article.download()
                article.parse()
                combined_news += f"{article.text}\n"
            except:
                pass
    return combined_news.strip()  # remove trailing newline
    

