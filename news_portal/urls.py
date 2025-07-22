from django.urls import path
from .views import show_news, get_news, search_news_api, analyze_url_api

app_name = "news_portal"

urlpatterns = [
    path('', show_news, name='show_news'),
    path('api/search/', search_news_api, name='search_news_api'),
    path('api/analyze/', analyze_url_api, name='analyze_url_api'),
    path('get_news', get_news, name='get_news'),
]
