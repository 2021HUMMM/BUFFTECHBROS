from django.conf import settings
from django.shortcuts import render
from django.http import JsonResponse
import requests
from newspaper import Article
from analyzer.views import get_keywords
from datetime import datetime, timedelta
import re


def show_news(request):
    search_query = request.GET.get('search', '')
    category = request.GET.get('category', '')
    news_url = request.GET.get('news_url', '')
    analyze_url = request.GET.get('analyze_url', '')
    
    # Get trending news with search and category filters
    trending_news = get_trending_news(search_query, category)
    
    # Analyze URL if provided
    analyzed_article = None
    if news_url and analyze_url:
        analyzed_article = analyze_news_url(news_url)

    context = {
        'trending_news': trending_news,
        'search_query': search_query,
        'category': category,
        'analyzed_article': analyzed_article,
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

def analyze_url_api(request):
    """API endpoint for AJAX URL analysis"""
    news_url = request.GET.get('url', '')
    
    if not news_url:
        return JsonResponse({
            'success': False,
            'error': 'No URL provided'
        })
    
    # Analyze the URL
    analyzed_article = analyze_news_url(news_url)
    
    return JsonResponse({
        'success': True,
        'article': analyzed_article
    })

def get_trending_news(search_query='', category=''):
    url = "https://newsdata.io/api/1/news"
    params = {
        "apikey": settings.NEWS_API_KEY_2,
        "country": "id",         # Fokus ke Indonesia
        "language": "id",        # Bahasa Indonesia
        "category": "top",       
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
    
def find_related_news(keywords, publish_date, limit=10):
    """Find related news based on keywords with local date and similarity filtering"""
    if not keywords:
        return []
    
    # Calculate target date for filtering
    target_date = None
    if publish_date:
        if isinstance(publish_date, str):
            try:
                # Handle various date formats
                target_date = datetime.fromisoformat(publish_date.replace('Z', '+00:00'))
            except:
                try:
                    target_date = datetime.strptime(publish_date[:10], '%Y-%m-%d')
                except:
                    target_date = datetime.now()
        elif isinstance(publish_date, datetime):
            target_date = publish_date
        else:
            target_date = datetime.now()
    else:
        target_date = datetime.now()
    
    # Prepare search query from top keywords
    top_keywords = keywords[:3] if len(keywords) >= 3 else keywords
    search_query = " OR ".join(top_keywords) if len(top_keywords) > 1 else top_keywords[0] if top_keywords else ""
    
    if not search_query:
        return []
    
    # Use regular news endpoint (not archive)
    url = "https://newsdata.io/api/1/news"
    params = {
        "apikey": settings.NEWS_API_KEY_2,
        "q": search_query,
    }

    print(f"Searching for related news with keywords: {top_keywords}")
    print(f"Target date for filtering: {target_date}")
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        results = data.get("results", [])
        
        # If no results, try with global language
        if not results:
            params["language"] = "en"
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])
        
        # Filter and score results locally
        filtered_results = []
        
        for article in results:
            # Parse article date
            article_date = None
            pub_date = article.get('pubDate')
            if pub_date:
                try:
                    article_date = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                except:
                    try:
                        article_date = datetime.strptime(pub_date[:10], '%Y-%m-%d')
                    except:
                        continue
            
            # Check if article is within ±1 day
            if article_date and target_date:
                date_diff = abs((article_date - target_date).days)
                if date_diff > 1:
                    continue
            
            # Calculate keyword similarity
            article_text = f"{article.get('title', '')} {article.get('description', '')}".lower()
            keyword_matches = 0
            
            for keyword in keywords:
                if keyword.lower() in article_text:
                    keyword_matches += 1
            
            # Calculate similarity percentage
            similarity = (keyword_matches / len(keywords)) * 100 if keywords else 0
            
            # Only include articles with 50%+ similarity
            if similarity >= 50:
                article['similarity_score'] = similarity
                filtered_results.append(article)
        
        # Sort by similarity score (descending) and limit results
        filtered_results.sort(key=lambda x: x.get('similarity_score', 0), reverse=True)
        
        print(f"Found {len(filtered_results)} related articles with 50%+ similarity")
        
        return filtered_results[:limit]
        
    except requests.exceptions.RequestException as e:
        print(f"Error finding related news: {e}")
        return []

def analyze_news_url(url):
    """Analyze a news article from URL and find related news"""
    try:
        # Download and parse the article
        article = Article(url)
        article.download()
        article.parse()
        
        # Extract keywords using the analyzer
        keywords = get_keywords(article.text)
        keywords_list = keywords if isinstance(keywords, list) else [str(keywords)]
        
        # Find related news based on keywords and date
        related_news = find_related_news(keywords_list, article.publish_date)
        
        # Return structured data
        return {
            'url': url,
            'title': article.title,
            'summary': article.summary if hasattr(article, 'summary') else article.text[:200] + "...",
            'publish_date': article.publish_date,
            'keywords': keywords_list[:10],  # Limit to top 10 keywords
            'text': article.text,
            'authors': article.authors,
            'related_news': related_news,
            'search_info': {
                'target_date': article.publish_date.strftime('%Y-%m-%d') if article.publish_date else 'Unknown',
                'date_range': '±1 day from publish date',
                'keywords_used': keywords_list[:3],
                'similarity_threshold': '50%',
                'total_found': len(related_news)
            }
        }
        
    except Exception as e:
        print(f"Error analyzing URL {url}: {e}")
        return {
            'url': url,
            'title': 'Error analyzing article',
            'summary': f'Could not analyze the article. Error: {str(e)}',
            'publish_date': None,
            'keywords': [],
            'text': '',
            'authors': [],
            'related_news': [],
            'search_info': {
                'target_date': 'Unknown',
                'date_range': 'N/A',
                'keywords_used': [],
                'similarity_threshold': '50%',
                'total_found': 0
            }
        }

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


