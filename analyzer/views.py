from django.conf import settings
from django.shortcuts import render
from django.http import JsonResponse
import openai
import requests
from newspaper import Article
from datetime import datetime, timedelta
import re

# Create your views here.

openai.api_key = settings.OPENAI_API_KEY
client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)


def calculate_article_similarity(article, keywords, target_date, article_date):
    """Calculate similarity score with multiple factors including full article text"""
    
    # Get article text components
    article_title = (article.get('title') or '').lower()
    article_desc = (article.get('description') or '').lower()
    
    print(f"  🔍 Analyzing: {article.get('title', 'No title')[:60]}...")
    print(f"     Keywords to match: {keywords}")
    
    if not article_title and not article_desc:
        print(f"     ❌ No title or description found")
        return 0
    
    # Initialize scores
    title_score = 0
    desc_score = 0
    content_score = 0
    exact_matches = 0
    partial_matches = 0
    
    # Try to get full article content using newspaper
    full_content = ""
    article_url = article.get('link')
    if article_url:
        try:
            print(f"     📰 Fetching full content from: {article_url[:50]}...")
            news_article = Article(article_url)
            news_article.download()
            news_article.parse()
            full_content = news_article.text.lower() if news_article.text else ""
            print(f"     ✅ Content fetched: {len(full_content)} chars")
        except Exception as e:
            print(f"     ❌ Failed to fetch content: {str(e)[:50]}...")
            full_content = ""
    else:
        print(f"     ⚠️  No URL provided for content fetching")
    
    # Calculate keyword matches
    for keyword in keywords:
        keyword_lower = str(keyword).lower()
        print(f"     🔎 Checking keyword: '{keyword_lower}'")
        
        # Title matches (weighted higher)
        if article_title:
            if keyword_lower in article_title:
                # Check if it's an exact word match (not just substring)
                if re.search(r'\b' + re.escape(keyword_lower) + r'\b', article_title):
                    title_score += 1
                    exact_matches += 1
                    print(f"        ✅ Title EXACT match: +1.0 point")
                else:
                    title_score += 0.5
                    partial_matches += 1
                    print(f"        ⚡ Title partial match: +0.5 point")
            else:
                print(f"        ❌ No title match")
        
        # Description matches
        if article_desc:
            if keyword_lower in article_desc:
                if re.search(r'\b' + re.escape(keyword_lower) + r'\b', article_desc):
                    desc_score += 1
                    exact_matches += 0.5  # Less weight for desc exact matches
                    print(f"        ✅ Description EXACT match: +1.0 point")
                else:
                    desc_score += 0.5
                    partial_matches += 0.5
                    print(f"        ⚡ Description partial match: +0.5 point")
            else:
                print(f"        ❌ No description match")
        
        # Full content matches (if available)
        if full_content:
            if keyword_lower in full_content:
                # Count exact word matches in content
                exact_content_matches = len(re.findall(r'\b' + re.escape(keyword_lower) + r'\b', full_content))
                if exact_content_matches > 0:
                    # Score based on frequency, but cap it to avoid over-weighting
                    content_points = min(exact_content_matches * 0.5, 2.0)  # Max 2 points per keyword
                    content_score += content_points
                    exact_matches += min(exact_content_matches * 0.2, 0.5)  # Small bonus for content matches
                    print(f"        ✅ Content matches: {exact_content_matches}x = +{content_points} points")
                else:
                    print(f"        ⚡ Content partial match found")
            else:
                print(f"        ❌ No content match")
        else:
            print(f"        ⚠️  No content available for analysis")
    
    # Calculate weighted score
    total_keywords = len(keywords)
    
    # Component scores (out of 100)
    title_component = (title_score / total_keywords) * 50  # Title weight: 50% (reduced to make room for content)
    desc_component = (desc_score / total_keywords) * 20   # Description weight: 20%
    content_component = (content_score / total_keywords) * 25  # Content weight: 25% (new component)
    exact_bonus = (exact_matches / total_keywords) * 10   # Exact match bonus: 10%
    
    print(f"     📊 Raw scores - Title: {title_score}, Desc: {desc_score}, Content: {content_score}, Exact: {exact_matches}")
    print(f"     🧮 Weighted scores - Title: {title_component:.1f}, Desc: {desc_component:.1f}, Content: {content_component:.1f}, Bonus: {exact_bonus:.1f}")
    
    # Date proximity bonus (expanded range)
    date_bonus = 0
    if article_date and target_date:
        date_diff = abs((article_date - target_date).days)
        if date_diff == 0:
            date_bonus = 10  # Same day bonus
            print(f"     📅 Date bonus: +{date_bonus} (same day)")
        elif date_diff <= 1:
            date_bonus = 8   # Within 1 day bonus
            print(f"     📅 Date bonus: +{date_bonus} (±1 day)")
        elif date_diff <= 3:
            date_bonus = 5   # Within 3 days bonus
            print(f"     📅 Date bonus: +{date_bonus} (±{date_diff} days)")
        elif date_diff <= 7:
            date_bonus = 3   # Within 1 week bonus
            print(f"     📅 Date bonus: +{date_bonus} (±{date_diff} days)")
        else:
            print(f"     📅 No date bonus (±{date_diff} days)")
    else:
        print(f"     📅 No date comparison available")
    
    # Final score
    final_score = title_component + desc_component + content_component + exact_bonus + date_bonus
    capped_score = min(final_score, 100)  # Cap at 100
    
    print(f"     🏆 Final score: {final_score:.1f} (capped: {capped_score:.1f})")
    
    # Store analysis details for debugging
    article['analysis_details'] = {
        'title_score': round(title_component, 1),
        'desc_score': round(desc_component, 1), 
        'content_score': round(content_component, 1),
        'exact_bonus': round(exact_bonus, 1),
        'date_bonus': date_bonus,
        'has_full_content': len(full_content) > 0,
        'content_length': len(full_content)
    }
    
    return capped_score


def find_related_news(keywords, publish_date, original_url=None, limit=10):
    """Find related news with improved similarity algorithm"""
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
    
    # Prepare search query with length limit (NewsData.io has 100 char limit)
    selected_keywords = []
    query_length = 0
    
    for keyword in keywords[:6]:  # Start with max 6 keywords
        keyword_str = str(keyword).strip()
        # Calculate length if we add this keyword (including " OR " separator)
        additional_length = len(keyword_str) + (4 if selected_keywords else 0)  # " OR " = 4 chars
        
        if query_length + additional_length <= 95:  # Leave some buffer (95 instead of 100)
            selected_keywords.append(keyword_str)
            query_length += additional_length
        else:
            print(f"⚠️  Skipping keyword '{keyword_str}' - would exceed 100 char limit")
            break
    
    search_query = " OR ".join(selected_keywords) if len(selected_keywords) > 1 else selected_keywords[0] if selected_keywords else ""
    
    print(f"🔍 Query constructed: '{search_query}' (length: {len(search_query)})")
    
    if not search_query:
        print(f"❌ No valid search query could be constructed")
        return []
    
    if len(search_query) > 100:
        # Fallback: use only the first keyword if still too long
        search_query = selected_keywords[0] if selected_keywords else keywords[0]
        selected_keywords = [search_query]
        print(f"⚠️  Query still too long, using single keyword: '{search_query}'")
    
    # Use regular news endpoint
    url = "https://newsdata.io/api/1/news"
    params = {
        "apikey": settings.NEWS_API_KEY_2,
        "q": search_query,
        # Removed 'size' parameter as it's not supported
    }

    print(f"🔍 Searching for related news with keywords: {selected_keywords}")
    print(f"📅 Target date for filtering: {target_date}")
    print(f"🌐 API URL: {url}")
    print(f"📋 Query parameters: {params}")
    
    try:
        response = requests.get(url, params=params)
        print(f"📞 Request URL: {response.url}")
        print(f"📊 Response status: {response.status_code}")
        response.raise_for_status()
        data = response.json()
        results = data.get("results", [])
        print(f"📰 Initial results count: {len(results)}")
        
        # If no results, try with global language
        if not results:
            print(f"⚠️  No results found, trying with global English...")
            params["language"] = "en"
            response = requests.get(url, params=params)
            print(f"📞 Fallback request URL: {response.url}")
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])
            print(f"📰 Fallback results count: {len(results)}")
        
        # Filter and score results with improved algorithm
        filtered_results = []
        
        print(f"🧮 Starting similarity analysis for {len(results)} articles...")
        for i, article in enumerate(results, 1):
            print(f"\n📄 Article {i}/{len(results)}:")
            
            # Skip if this is the same article (check URL)
            article_url = article.get('link', '')
            if original_url and article_url and article_url.strip() == original_url.strip():
                print(f"  🔄 SKIPPING: This is the original article being analyzed")
                continue
            
            # Parse article date
            article_date = None
            pub_date = article.get('pubDate')
            if pub_date:
                try:
                    article_date = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                    print(f"  📅 Article date: {article_date.strftime('%Y-%m-%d')}")
                except:
                    try:
                        article_date = datetime.strptime(pub_date[:10], '%Y-%m-%d')
                        print(f"  📅 Article date: {article_date.strftime('%Y-%m-%d')}")
                    except:
                        print(f"  ⚠️  Could not parse date: {pub_date}")
                        pass  # Don't skip, just no date bonus
            else:
                print(f"  ❌ No publication date available")
            
            # Calculate advanced similarity score
            score = calculate_article_similarity(article, selected_keywords, target_date, article_date)
            
            # Dynamic threshold based on number of keywords used
            if len(selected_keywords) >= 4:
                min_score = 35  # Higher threshold for many keywords
            elif len(selected_keywords) >= 2:
                min_score = 25  # Medium threshold
            else:
                min_score = 20  # Lower threshold for few keywords
            
            print(f"  🎯 Score: {score:.1f} (threshold: {min_score})")
            
            if score >= min_score:
                article['similarity_score'] = round(score, 1)
                article['is_recent'] = article_date and target_date and abs((article_date - target_date).days) <= 3  # Expanded from 1 to 3 days
                filtered_results.append(article)
                print(f"  ✅ Article ACCEPTED (score >= {min_score})")
            else:
                print(f"  ❌ Article REJECTED (score < {min_score})")
        
        # Sort by similarity score (descending) and prioritize recent articles
        print(f"\n📊 Sorting {len(filtered_results)} accepted articles...")
        filtered_results.sort(key=lambda x: (x.get('is_recent', False), x.get('similarity_score', 0)), reverse=True)
        
        # Debug logging
        print(f"\n🏆 FINAL RESULTS:")
        print(f"Found {len(filtered_results)} related articles (min score varies by keyword count)")
        print(f"📊 Top {min(5, len(filtered_results))} results:")
        for i, result in enumerate(filtered_results[:5]):
            title = result.get('title') or 'No title'
            score = result.get('similarity_score', 0)
            recent = result.get('is_recent', False)
            analysis = result.get('analysis_details', {})
            content_info = f"📄{analysis.get('content_length', 0)}chars" if analysis.get('has_full_content') else "📋no-content"
            print(f"  {i+1}. [{score}] {'⏰' if recent else '🕐'} {content_info} T:{analysis.get('title_score', 0)} D:{analysis.get('desc_score', 0)} C:{analysis.get('content_score', 0)} - {title[:50]}...")
        
        print(f"🎯 Returning top {limit} results\n")
        
        # Store selected keywords info in the results for reference
        if filtered_results:
            for result in filtered_results:
                if 'analysis_details' not in result:
                    result['analysis_details'] = {}
                result['analysis_details']['search_keywords_used'] = selected_keywords
        
        return filtered_results[:limit]
        
    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR finding related news: {e}")
        print(f"🔧 Check API key and network connection")
        return []


def analyze_news_url(url, manual_publish_date=None):
    """Analyze a news article from URL and find related news"""
    print(f"\n🚀 Starting URL analysis for: {url}")
    try:
        # Download and parse the article
        print(f"📰 Downloading article content...")
        article = Article(url)
        article.download()
        article.parse()
        
        print(f"✅ Article parsed successfully:")
        print(f"  📰 Title: {article.title}")
        print(f"  📅 Publish date: {article.publish_date}")
        print(f"  👥 Authors: {article.authors}")
        print(f"  📝 Text length: {len(article.text)} characters")
        
        # Use manual publish date if provided, otherwise use article's publish date
        final_publish_date = None
        if manual_publish_date:
            try:
                # Parse manual date string to datetime object
                final_publish_date = datetime.strptime(manual_publish_date, '%Y-%m-%d')
                print(f"  🗓️  Using manual publish date: {final_publish_date}")
            except ValueError:
                print(f"  ⚠️  Invalid manual date format, using article date")
                final_publish_date = article.publish_date
        else:
            final_publish_date = article.publish_date
            print(f"  📅 Using article's publish date: {final_publish_date}")
        
        # Extract keywords using the analyzer
        print(f"🔍 Extracting keywords from article text...")
        keywords = get_keywords(article.text)
        keywords_list = keywords if isinstance(keywords, list) else [str(keywords)]
        print(f"🏷️  Keywords extracted: {keywords_list}")
        
        # Find related news based on keywords and date
        print(f"🔗 Finding related news...")
        related_news = find_related_news(keywords_list, final_publish_date, url)
        
        # Extract selected keywords from search results if available
        search_keywords_used = keywords_list[:6]  # Default fallback
        if related_news and len(related_news) > 0:
            # Get keywords actually used from first result's analysis details
            first_result_analysis = related_news[0].get('analysis_details', {})
            if 'search_keywords_used' in first_result_analysis:
                search_keywords_used = first_result_analysis['search_keywords_used']
        
        print(f"✅ Analysis completed successfully!")
        print(f"📊 Results summary:")
        print(f"  🏷️  Keywords found: {len(keywords_list)}")
        print(f"  📰 Related articles: {len(related_news)}")
        
        # Return structured data
        return {
            'url': url,
            'title': article.title,
            'summary': article.summary if hasattr(article, 'summary') else article.text[:200] + "...",
            'publish_date': final_publish_date,  # Use the final determined publish date
            'original_publish_date': article.publish_date,  # Keep original for reference
            'manual_date_used': manual_publish_date is not None,  # Flag to show if manual date was used
            'keywords': keywords_list[:10],  # Show top 10 keywords
            'text': article.text,
            'authors': article.authors,
            'related_news': related_news,
            'search_info': {
                'target_date': final_publish_date.strftime('%Y-%m-%d') if final_publish_date else 'Unknown',
                'date_range': 'Prioritized within ±3 days, bonus up to ±7 days',
                'keywords_used': search_keywords_used,  # Show keywords actually used in search
                'similarity_method': 'Advanced weighted scoring with full content',
                'total_found': len(related_news),
                'manual_date_override': f"Manual date: {manual_publish_date}" if manual_publish_date else "Auto-detected from article",
                'scoring_details': {
                    'title_weight': '50%',
                    'description_weight': '20%',
                    'content_weight': '25%', 
                    'exact_match_bonus': '10%',
                    'date_bonus': '3-10 points (same day=10, ±1day=8, ±3days=5, ±7days=3)',
                    'method': 'Full article content analysis'
                }
            }
        }
        
    except Exception as e:
        print(f"❌ Error analyzing URL {url}: {e}")
        print(f"🔧 Check URL validity and network connection")
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
                'similarity_method': 'Advanced weighted scoring with full content',
                'total_found': 0,
                'scoring_details': {
                    'title_weight': '50%',
                    'description_weight': '20%',
                    'content_weight': '25%', 
                    'exact_match_bonus': '10%',
                    'date_bonus': '3-10 points (same day=10, ±1day=8, ±3days=5, ±7days=3)',
                    'method': 'Full article content analysis'
                }
            }
        }


def analyze_url_api(request):
    """API endpoint for AJAX URL analysis"""
    news_url = request.GET.get('url', '')
    publish_date = request.GET.get('publish_date', '')  # Get manual publish date
    
    print(f"\n🌐 API Request received:")
    print(f"   📍 URL to analyze: {news_url}")
    print(f"   📅 Manual publish date: {publish_date if publish_date else 'Not provided'}")
    print(f"   🔧 Request method: {request.method}")
    print(f"   📊 All GET parameters: {dict(request.GET)}")
    
    if not news_url:
        print(f"❌ No URL provided in request")
        return JsonResponse({
            'success': False,
            'error': 'No URL provided'
        })
    
    # Analyze the URL with optional manual publish date
    print(f"🚀 Starting URL analysis...")
    analyzed_article = analyze_news_url(news_url, publish_date if publish_date else None)
    
    print(f"✅ Analysis completed, sending response")
    return JsonResponse({
        'success': True,
        'article': analyzed_article
    })


def get_keywords(page_string):
    print(f"\n🤖 Starting keyword extraction...")
    print(f"📝 Text length: {len(page_string)} characters")
    print(f"📄 Text preview: {page_string[:200]}...")
    
    reply = None
    user_input = """Here's a news article. i want you to extract the keywords from it to a csv string format.
                    adapt to its original language, if it's in indonesian, return it in indonesian, if it's 
                    in english, return it in english. the goal is to extract the most relevant keywords that 
                    represent the content of the article for me to then forward it to a news api to find similar news.
                    
                    heres an example of the result im hoping you to return: 'keyword1, keyword2, keyword3'

                    do not return any other text, just the keywords in csv string format, not a csv file.
                    
                    here's the article:\n{}""".format(page_string)
    
    try:
        print(f"🔄 Sending request to OpenAI GPT-4o...")
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "user", "content": user_input}
            ]
        )
        
        reply = str(response.choices[0].message.content.strip())
        print(f"🤖 OpenAI raw response: {reply}")
        
        reply = reply.replace("'", "").replace('"', '').replace("\n", "")
        print(f"🧹 Cleaned response: {reply}")

        # turn reply into a list of keywords
        keywords = [keyword.strip() for keyword in reply.split(',') if keyword.strip()]
        print(f"🏷️  Final keywords list: {keywords}")
        print(f"📊 Total keywords extracted: {len(keywords)}")

        return keywords
        
    except Exception as e:
        print(f"❌ Error in keyword extraction: {e}")
        print(f"🔧 Falling back to empty keywords list")
        return []



# def test_chat(request):
#     reply = None
#     user_input = None

#     if request.method == 'POST':
#         user_input = request.POST.get('message')
#         if user_input:
#             response = client.chat.completions.create(
#                 model="gpt-4o",  # atau "gpt-3.5-turbo"
#                 messages=[
#                     {"role": "user", "content": user_input}
#                 ]
#             )
#             reply = response.choices[0].message.content

#     return render(request, 'test_chat.html', {
#         'user_input': user_input,
#         'reply': reply
#     })
    