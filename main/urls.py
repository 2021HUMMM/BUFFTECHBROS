from django.urls import path
from main.views import (
    show_main,
    test_chat,
    main_page,
)
app_name = 'main'

urlpatterns = [
    path('', show_main, name='show_main'),
    path('test-gpt/', test_chat, name='test_chat'),
    path('landing/', main_page, name='main_page'),
]