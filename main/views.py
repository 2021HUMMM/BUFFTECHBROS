from django.shortcuts import render
from newsapi import NewsApiClient
from django.conf import settings


# Create your views here.

def show_main(request):
    # Get news data
    news_data = get_news(request, "bitcoin")
    # Pass news data to the template
    context = {
        'news_data': news_data['articles']
    }
    return render(request, 'main.html', context)

def get_news(request, topic):
    newsapi = NewsApiClient(settings.NEWS_API_KEY)
    # get bahasa indonesia news
    data = newsapi.get_everything(q=topic, language='en', page_size=5)
    return data