from django.urls import path
from .views import show_news, get_news, combine_news, search_news_api

app_name = "news_portal"

urlpatterns = [
    path('', show_news, name='show_news'),
    path('api/search/', search_news_api, name='search_news_api'),
    path('get_news', get_news, name='get_news'),
    path('combine_news', combine_news, name='combine_news'),
]
