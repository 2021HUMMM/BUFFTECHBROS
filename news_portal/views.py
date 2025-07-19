from django.conf import settings
from django.shortcuts import render
from django.http import JsonResponse
import requests
from newspaper import Article

def show_news(request):
    search_query = request.GET.get('search', '')
    category = request.GET.get('category', '')
    
    # Get trending news with search and category filters
    trending_news = get_trending_news(search_query, category)

    context = {
        'trending_news': trending_news,
        'search_query': search_query,
        'category': category,
    }
    return render(request, 'news.html', context)

def search_news_api(request):
    """API endpoint for AJAX search"""
    search_query = request.GET.get('search', '')
    category = request.GET.get('category', '')
    
    # Get trending news with search filters
    trending_news = get_trending_news(search_query, category)
    
    # Format data for JSON response
    news_list = []
    for news in trending_news:
        news_data = {
            'title': news.get('title', ''),
            'description': news.get('description', ''),
            'link': news.get('link', ''),
            'source': news.get('source_id', ''),
            'source_icon': news.get('source_icon', ''),
            'pubDate': news.get('pubDate', ''),
            'image_url': news.get('image_url', ''),
        }
        news_list.append(news_data)
    
    return JsonResponse({
        'success': True,
        'news': news_list,
        'count': len(news_list),
        'search_query': search_query,
        'category': category
    })

def get_trending_news(search_query='', category=''):
    url = "https://newsdata.io/api/1/news"
    params = {
        "apikey": settings.NEWS_API_KEY_2,
        "country": "id",         # Fokus ke Indonesia
        "language": "id",        # Bahasa Indonesia
        "category": "top",       # bisa juga 'business', 'politics', dll
    }
    
    # Add search query if provided
    if search_query:
        params["q"] = search_query
    
    # Add category filter if provided
    if category:
        params["category"] = category

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        results = data.get("results", [])
        
        # If we have a search query but no results, try with broader search
        if search_query and not results:
            # Try without category filter first
            if category:
                params_backup = params.copy()
                del params_backup["category"]
                response = requests.get(url, params=params_backup)
                response.raise_for_status()
                data = response.json()
                results = data.get("results", [])
            
            # If still no results, try with global search
            if not results:
                params_global = {
                    "apikey": settings.NEWS_API_KEY_2,
                    "q": search_query,
                    "language": "en",  # Try English for broader results
                }
                response = requests.get(url, params=params_global)
                response.raise_for_status()
                data = response.json()
                results = data.get("results", [])
        
        return results
        
    except requests.exceptions.RequestException as e:
        print("Trending News Fetch Error:", e)
        return []


def get_news(topic):
    url = "https://newsdata.io/api/1/latest"
    params = {
        "apikey": settings.NEWS_API_KEY_2,
        "q": topic,
        "language": "id",  # optional, can also use 'id' for Indonesian
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()  # raise error for bad response (4xx/5xx)
        data = response.json()
        return data.get("results", [])  # safely get list of articles
    except requests.exceptions.RequestException as e:
        print("NewsData API Error:", e)
        return []
    
def combine_news(data):
    combined_news = ""
    if data:
        for article in data:
            try:
                url = article["link"]
                article = Article(url)
                article.download()
                article.parse()
                combined_news += f"{article.text}\n"
            except:
                pass
    return combined_news.strip()  # remove trailing newline
    

