from django.urls import path
from analyzer.views import (
    get_keywords,
    analyze_url_api,
    analyze_news_url,
    ai_comparison_api,
    analyze_ocr_api,
    analyze_image_api,
    analyze_url_ajax,
    generate_ai_content_summary_api
)

app_name = 'analyzer'

urlpatterns = [
    path('get_keywords/<str:page_string>/', get_keywords, name='get_keywords'),
    path('analyze_url_api/', analyze_url_api, name='analyze_url_api'),
    path('analyze_news_url/<path:url>/', analyze_news_url, name='analyze_news_url'),
    path('ai_comparison/', ai_comparison_api, name='ai_comparison'),
    path('analyze-ocr-api/', analyze_ocr_api, name='analyze_ocr_api'),
    path('analyze-image-api/', analyze_image_api, name='analyze_image_api'),
    path('analyze-url-ajax/', analyze_url_ajax, name='analyze_url_ajax'),
    path('generate-ai-content-summary/', generate_ai_content_summary_api, name='generate_ai_content_summary'),
]