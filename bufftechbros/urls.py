from django.contrib import admin
from django.urls import include, path

from main.views import main_redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    
    path('', main_redirect, name='root'),
    path('auth/', include('authentication.urls')),
    path('main/', include('main.urls')),
    path('news/', include('news_portal.urls')),
    path('analyzer/', include('analyzer.urls')),
]
