from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    
    path('', include('authentication.urls')),
    path('main/', include('main.urls')),
    path('news/', include('news_portal.urls')),
    path('analyzer/', include('analyzer.urls')),
]
