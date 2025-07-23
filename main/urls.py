from django.urls import path
from main.views import (
    main_page,
)
app_name = 'main'

urlpatterns = [
    path('', main_page, name='main_page'),
]