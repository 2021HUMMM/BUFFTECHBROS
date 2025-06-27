from django.urls import path
from .views import (
    read_image,
)
app_name = 'OCRTool'

urlpatterns = [
    path('', read_image, name='read_image'),
]