from django.urls import path
from .views import (
    show_main,
)
app_name = 'authentication'

urlpatterns = [
    path('', show_main, name='main'),
]