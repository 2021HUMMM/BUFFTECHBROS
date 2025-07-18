# urls for authentication app
from django.urls import path
from .views import (
    login_user,
    register_user,
    logout_user,
)
app_name = 'authentication'

urlpatterns = [
    path('', login_user, name='login'),
    path('register/', register_user, name='register'),
    path('logout/', logout_user, name='logout'),
]