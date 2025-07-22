from django.urls import path
from analyzer.views import (
    get_keywords,
    analyze_url_api,
    analyze_news_url
)

app_name = 'analyzer'

urlpatterns = [
    path('get_keywords/<str:page_string>/', get_keywords, name='get_keywords'),
    path('analyze_url_api/', analyze_url_api, name='analyze_url_api'),
    path('analyze_news_url/<path:url>/', analyze_news_url, name='analyze_news_url'),
]