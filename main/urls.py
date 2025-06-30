from django.urls import path
from .views import (
    show_main,
    test_chat,
)
app_name = 'main'

urlpatterns = [
    path('', show_main, name='show_main'),
    path('test-gpt/', test_chat, name='test_chat'),
]