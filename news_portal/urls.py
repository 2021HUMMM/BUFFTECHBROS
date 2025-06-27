from django.urls import path
from .views import show_news

app_name = "news_portal"

urlpatterns = [
    path('', show_news, name='show_news'),
]
