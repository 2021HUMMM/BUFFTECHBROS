from django.urls import path
from main.views import (
    show_main,
    test_chat,
    landing_page,
    main_redirect,
)
app_name = 'main'

urlpatterns = [
    path('', show_main, name='show_main'),
    path('test-gpt/', test_chat, name='test_chat'),
    path('landing/', landing_page, name='landing_page'),
    path('redirect/', main_redirect, name='main_redirect'),
]