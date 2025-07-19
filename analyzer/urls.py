from django.urls import path
from analyzer.views import (
    get_keywords
)
app_name = 'main'

urlpatterns = [
    path('get_keywords/<str:page_string>/', get_keywords, name='get_keywords'),
]