from django.conf import settings
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import openai
import requests
import json
from newspaper import Article
from datetime import datetime, timedelta
import re

# Create your views here.

openai.api_key = settings.OPENAI_API_KEY
client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)


def analyze_sentiment_disagreement(original_text, related_article, keywords):
    """Analyze sentiment disagreement between original article and related article"""
    
    print(f"🎭 Starting sentiment analysis for: {related_article.get('title', 'No title')[:50]}...")
    
    # Get related article content
    related_content = ""
    article_url = related_article.get('link')
    
    if article_url:
        try:
            print(f"     📰 Fetching content for sentiment analysis...")
            news_article = Article(article_url)
            news_article.download()
            news_article.parse()
            related_content = news_article.text if news_article.text else ""
            print(f"     ✅ Content fetched: {len(related_content)} chars")
        except Exception as e:
            print(f"     ❌ Failed to fetch content: {str(e)[:50]}...")
            # Fallback to title + description
            related_content = f"{related_article.get('title', '')} {related_article.get('description', '')}"
    else:
        # Fallback to title + description
        related_content = f"{related_article.get('title', '')} {related_article.get('description', '')}"
    
    # If no content available, skip analysis
    if not related_content.strip():
        print(f"     ❌ No content available for sentiment analysis")
        return {
            'disagreement_score': 0,
            'sentiment_original': 'neutral',
            'sentiment_related': 'neutral',
            'disagreement_level': 'unknown',
            'confidence': 0,
            'analysis_summary': 'No content available for analysis',
            'reason': 'Cannot analyze sentiment - no article content available for comparison'
        }
    
    # Create prompt for GPT-4 to analyze sentiment disagreement
    prompt = f"""
    Analyze the sentiment and disagreement level between these two news articles about similar topics. The more those two articles have different opinions regarding the same topic,
    the higher the disagreement score should be. for example, if one article's tone toward the topic is positive and the other is negative, the disagreement score should be high.
    
    KEYWORDS CONTEXT: {', '.join(keywords[:5])}
    
    ORIGINAL ARTICLE:
    {original_text[:2000]}...
    
    RELATED ARTICLE:
    {related_content[:2000]}...
    
    Please analyze:
    1. The sentiment of each article (positive/negative/neutral)
    2. How much they disagree with each other on the main topic
    3. Give a disagreement score from 0-100 (0=complete agreement, 100=complete disagreement)
    4. Provide a clear reason explaining why you gave this disagreement score
    
    Respond in this exact JSON format:
    {{
        "disagreement_score": <number 0-100>,
        "sentiment_original": "<positive/negative/neutral>",
        "sentiment_related": "<positive/negative/neutral>",
        "disagreement_level": "<high/medium/low/minimal>",
        "confidence": <number 0-100>,
        "analysis_summary": "<brief explanation of the disagreement or agreement>",
        "reason": "<detailed explanation of why this disagreement score was given, mentioning specific points of agreement or disagreement>"
    }}
    """
    
    try:
        print(f"     🤖 Sending to OpenAI for sentiment analysis...")
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.3  # Lower temperature for more consistent analysis
        )
        
        response_text = response.choices[0].message.content.strip()
        print(f"     🤖 GPT-4 response: {response_text[:100]}...")
        
        # Clean response text - remove markdown code blocks if present
        cleaned_response = response_text
        
        # More robust cleaning for markdown code blocks
        if '```json' in cleaned_response:
            # Find and remove the opening ```json
            start_index = cleaned_response.find('```json')
            if start_index != -1:
                cleaned_response = cleaned_response[start_index + 7:]  # Remove '```json'
        
        if '```' in cleaned_response:
            # Find and remove the closing ```
            end_index = cleaned_response.rfind('```')
            if end_index != -1:
                cleaned_response = cleaned_response[:end_index]
        
        # Remove any remaining markdown artifacts
        cleaned_response = cleaned_response.strip()
        
        print(f"     🧹 Cleaned response: {cleaned_response[:100]}...")
        
        # Parse JSON response
        import json
        try:
            sentiment_data = json.loads(cleaned_response)
            print(f"     ✅ Sentiment analysis completed:")
            print(f"        📊 Disagreement score: {sentiment_data.get('disagreement_score', 0)}")
            print(f"        🎭 Original sentiment: {sentiment_data.get('sentiment_original', 'neutral')}")
            print(f"        🎭 Related sentiment: {sentiment_data.get('sentiment_related', 'neutral')}")
            print(f"        📈 Disagreement level: {sentiment_data.get('disagreement_level', 'unknown')}")
            print(f"        🧠 Confidence: {sentiment_data.get('confidence', 0)}%")
            print(f"        💭 Analysis summary: {sentiment_data.get('analysis_summary', 'No summary')}")
            print(f"        📝 Reason: {sentiment_data.get('reason', 'No reason provided')}...")
            return sentiment_data
            
        except json.JSONDecodeError as e:
            print(f"     ❌ Failed to parse JSON response, extracting manually...")
            print(f"     🔍 JSON Error: {str(e)}")
            print(f"     📄 Full response for debugging:")
            print(f"     {response_text}")
            print(f"     🧹 Cleaned response for debugging:")
            print(f"     {cleaned_response}")
            
            # Fallback parsing
            lines = response_text.split('\n')
            disagreement_score = 0
            for line in lines:
                if 'disagreement_score' in line.lower():
                    import re
                    numbers = re.findall(r'\d+', line)
                    if numbers:
                        disagreement_score = int(numbers[0])
                        break
            
            return {
                'disagreement_score': disagreement_score,
                'sentiment_original': 'neutral',
                'sentiment_related': 'neutral',
                'disagreement_level': 'medium' if disagreement_score > 50 else 'low',
                'confidence': 50,
                'analysis_summary': 'Partial analysis due to parsing issues',
                'reason': 'Could not parse full GPT response, extracted disagreement score only'
            }
            
    except Exception as e:
        print(f"     ❌ Error in sentiment analysis: {str(e)[:100]}...")
        return {
            'disagreement_score': 0,
            'sentiment_original': 'neutral',
            'sentiment_related': 'neutral',
            'disagreement_level': 'unknown',
            'confidence': 0,
            'analysis_summary': f'Analysis failed: {str(e)[:50]}...',
            'reason': f'Sentiment analysis failed due to API error: {str(e)[:100]}'
        }


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


def find_related_news(keywords, publish_date, original_url=None, original_text=None, limit=10):
    """Find related news with improved similarity algorithm and sentiment analysis sorting"""
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
        
        # Apply sentiment analysis if original text is provided
        if original_text and filtered_results:
            print(f"\n🎭 Starting sentiment analysis for disagreement sorting...")
            print(f"📊 Analyzing {len(filtered_results)} articles for sentiment disagreement...")
            
            for i, article in enumerate(filtered_results, 1):
                try:
                    print(f"\n🎭 Article {i}/{len(filtered_results)}: {article.get('title', 'Unknown')[:50]}...")
                    
                    # Perform sentiment analysis
                    sentiment_data = analyze_sentiment_disagreement(original_text, article, selected_keywords)
                    
                    if sentiment_data:
                        article['disagreement_score'] = sentiment_data.get('disagreement_score', 50)
                        article['sentiment_analysis'] = sentiment_data
                        print(f"   ✅ Disagreement score: {article['disagreement_score']}%")
                    else:
                        # Default neutral score if analysis fails
                        article['disagreement_score'] = 50
                        print(f"   ⚠️ Using default neutral score (50%)")
                        
                except Exception as e:
                    print(f"   ❌ Sentiment analysis failed: {str(e)[:50]}...")
                    article['disagreement_score'] = 50  # Default neutral
            
            # Sort by disagreement score (highest disagreement first)
            print(f"\n� Sorting {len(filtered_results)} articles by disagreement score...")
            filtered_results.sort(key=lambda x: x.get('disagreement_score', 50), reverse=True)
            
            # Show sorted results
            print(f"🏆 Articles sorted by disagreement (highest first):")
            for i, article in enumerate(filtered_results[:5]):  # Show top 5
                score = article.get('disagreement_score', 50)
                sim_score = article.get('similarity_score', 0)
                title = article.get('title', 'Unknown')[:40]
                print(f"   {i+1}. [{score}% disagreement, {sim_score} similarity] {title}...")
        
        else:
            # Fallback sorting by similarity score if no original text
            print(f"\n📈 Sorting {len(filtered_results)} articles by similarity score (no sentiment analysis)...")
            filtered_results.sort(key=lambda x: (x.get('is_recent', False), x.get('similarity_score', 0)), reverse=True)
            
            # Show sorted results
            print(f"🏆 Articles sorted by similarity:")
            for i, article in enumerate(filtered_results[:5]):  # Show top 5
                score = article.get('similarity_score', 0)
                recent = article.get('is_recent', False)
                title = article.get('title', 'Unknown')[:40]
                print(f"   {i+1}. [{score} similarity] {'⏰' if recent else '🕐'} {title}...")
        
        # Debug logging
        print(f"\n🏆 FINAL RESULTS:")
        print(f"Found {len(filtered_results)} related articles")
        if original_text:
            print(f"📊 Sorted by: Disagreement Score (sentiment analysis)")
        else:
            print(f"📊 Sorted by: Similarity Score + Recency")
        
        print(f"🎯 Returning top {limit} results\n")
        
        # Store selected keywords info in the results for reference
        if filtered_results:
            for result in filtered_results:
                if 'analysis_details' not in result:
                    result['analysis_details'] = {}
                result['analysis_details']['search_keywords_used'] = selected_keywords
                result['analysis_details']['has_sentiment_analysis'] = original_text is not None
        
        return filtered_results[:limit]
        
    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR finding related news: {e}")
        print(f"🔧 Check API key and network connection")
        return []


def generate_comparative_summary(original_article, related_articles):
    """Generate a comparative summary using ChatGPT for the original article and top disagreeing articles"""
    
    print(f"\n📝 Starting comparative summary generation...")
    print(f"📰 Original article: {original_article.get('title', 'No title')}...")
    print(f"📊 Related articles to analyze: {len(related_articles)}")
    
    if not related_articles:
        return {
            'summary': 'No related articles found for comparison.',
            'key_differences': [],
            'consensus_points': [],
            'disagreement_analysis': 'No disagreement analysis available.'
        }
    
    # Prepare article texts for analysis (limit to prevent token overflow)
    articles_text = f"ORIGINAL ARTICLE:\nTitle: {original_article.get('title', 'No title')}\n"
    articles_text += f"Content: {original_article.get('text', '')[:3000]}...\n\n"
    
    for i, article in enumerate(related_articles[:3], 1):  # Limit to top 3 disagreeing articles
        title = article.get('title', f'Article {i}')
        sentiment = article.get('sentiment_analysis', {})
        disagreement_score = sentiment.get('disagreement_score', 0)
        reason = sentiment.get('reason', 'No reason provided')
        
        # Get article content
        article_content = ""
        article_url = article.get('link')
        if article_url:
            try:
                news_article = Article(article_url)
                news_article.download()
                news_article.parse()
                article_content = news_article.text[:2000] if news_article.text else ""
            except:
                article_content = f"{article.get('title', '')} {article.get('description', '')}"
        else:
            article_content = f"{article.get('title', '')} {article.get('description', '')}"
        
        articles_text += f"RELATED ARTICLE {i} (Disagreement Score: {disagreement_score}):\nReason: {reason}\n"
        articles_text += f"Title: {title}\n"
        articles_text += f"Content: {article_content}...\n\n"
    
    # Create comprehensive prompt for GPT-4
    prompt = f"""
    Analyze and create a comparative analysis of these news articles about the same topic. 
    The articles are sorted by disagreement level (highest disagreement first). Respond like a professional news analyst.
    Do not respond like you are answering to a user, but rather as an expert analyzing the content. State that you are analyzing just the top 3 articles that disagree the most with the original article.
    When referring to a specific article, if it is the original article, refer to it as "ORIGINAL ARTICLE". If it is not (a related article), refer to it with its title.

    Here are the articles:
    
    {articles_text}
    
    Please provide a neutral, unbiased analysis comparison in the following structure:

    1. RELATED ARTICLES: List the titles of the related articles analyzed and their disagreement scores with the reasons for those scores.
    
    2. OVERVIEW: An analysis of what all articles are discussing
    
    3. KEY DISAGREEMENTS: List the main points where articles disagree with each other (if there are any)
    
    4. CONSENSUS POINTS: Points where most articles agree
    
    5. DIFFERENT PERSPECTIVES: How each article approaches the topic differently

    6. CONCLUSION: Your assessment of which perspective seems most balanced/credible

    Keep the analysis objective and highlight the most significant differences in viewpoints.
    Format your response in clear sections as requested above.
    """
    
    try:
        print(f"🤖 Sending to ChatGPT for comparative analysis...")
        print(f"📏 Total content length: {len(articles_text)} characters")
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2000
        )
        
        summary_text = response.choices[0].message.content.strip()
        print(f"✅ Comparative analysis generated successfully")
        print(f"📄 Summary length: {len(summary_text)} characters")
        
        # Parse the response into structured data
        sections = {}
        current_section = None
        current_content = []
        
        for line in summary_text.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            # Check if this line is a section header
            if any(header in line.upper() for header in ['RELATED ARTICLES', 'OVERVIEW', 'KEY DISAGREEMENTS', 'CONSENSUS POINTS', 'DIFFERENT PERSPECTIVES', 'FACTUAL ACCURACY', 'CONCLUSION']):
                # Save previous section
                if current_section and current_content:
                    sections[current_section] = '\n'.join(current_content)
                
                # Start new section
                current_section = line.replace(':', '').strip()
                current_content = []
            else:
                if current_section:
                    current_content.append(line)
        
        # Save last section
        if current_section and current_content:
            sections[current_section] = '\n'.join(current_content)
        
        return {
            'full_summary': summary_text,
            'sections': sections,
            'articles_analyzed': len(related_articles[:3]) + 1,  # +1 for original
            'highest_disagreement_score': related_articles[0].get('sentiment_analysis', {}).get('disagreement_score', 0) if related_articles else 0
        }
        
    except Exception as e:
        print(f"❌ Error generating comparative summary: {str(e)}")
        return {
            'full_summary': f'Error generating summary: {str(e)}',
            'sections': {},
            'articles_analyzed': 0,
            'highest_disagreement_score': 0
        }


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
        
        # Find related news based on keywords and date (no sentiment analysis for speed)
        print(f"🔗 Finding related news...")
        related_news = find_related_news(
            keywords_list, 
            final_publish_date, 
            original_url=url,
            original_text=None,  # Don't pass original text to skip sentiment analysis
            limit=10
        )
        
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
                'has_sentiment_analysis': False,  # No sentiment analysis in initial fetch
                'sorting_method': 'Similarity + Recency',  # Default sorting without sentiment
                'scoring_details': {
                    'title_weight': '50%',
                    'description_weight': '20%',
                    'content_weight': '25%', 
                    'exact_match_bonus': '10%',
                    'date_bonus': '3-10 points (same day=10, ±1day=8, ±3days=5, ±7days=3)',
                    'sentiment_analysis': 'Available via AI Comparison button',
                    'method': 'Full article content analysis (fast mode)'
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
                    'sentiment_analysis': 'Articles sorted by disagreement level (highest first)',
                    'method': 'Full article content + sentiment disagreement analysis'
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


@csrf_exempt
def ai_comparison_api(request):
    """
    API endpoint for generating AI comparison analysis
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)
    
    try:
        data = json.loads(request.body)
        article_url = data.get('article_url')
        article_title = data.get('article_title')
        article_text = data.get('article_text', '')
        related_articles = data.get('related_articles', [])
        
        if not article_url or not related_articles:
            return JsonResponse({
                'error': 'article_url and related_articles are required'
            }, status=400)
        
        print(f"🤖 Generating AI comparison for: {article_title}")
        print(f"📰 Analyzing {len(related_articles)} related articles")
        
        # Prepare original article data for analysis
        original_article = {
            'title': article_title,
            'text': article_text,
            'url': article_url
        }
        
        # Convert related articles to proper format and add sentiment analysis
        formatted_related_articles = []
        print(f"🎭 Starting sentiment analysis for AI comparison...")
        
        for i, article in enumerate(related_articles):
            formatted_article = {
                'title': article.get('title', ''),
                'link': article.get('link', ''),
                'description': article.get('description', ''),
                'source_id': article.get('source_id', ''),
                'pubDate': article.get('pubDate', ''),
                'similarity_score': article.get('similarity_score', 0)
            }
            
            # Perform sentiment analysis for AI comparison
            if article_text:  # Only if we have original article text
                try:
                    print(f"   🎭 Analyzing article {i+1}/{len(related_articles)}: {article.get('title', '')[:40]}...")
                    
                    # Use simplified keywords for sentiment analysis
                    keywords = [article_title] if article_title else []
                    sentiment_data = analyze_sentiment_disagreement(article_text, formatted_article, keywords)
                    
                    if sentiment_data:
                        formatted_article['sentiment_analysis'] = sentiment_data
                        formatted_article['disagreement_score'] = sentiment_data.get('disagreement_score', 50)
                        reason = sentiment_data.get('reason', 'No reason provided')
                        print(f"      ✅ Disagreement score: {sentiment_data.get('disagreement_score', 50)}%")
                        print(f"      💭 Reason: {reason}...")
                        print(f"      🎭 Sentiments: {sentiment_data.get('sentiment_original', 'neutral')} vs {sentiment_data.get('sentiment_related', 'neutral')}")
                    else:
                        formatted_article['disagreement_score'] = 50
                        print(f"      ⚠️ Using default neutral score")
                        
                except Exception as e:
                    print(f"      ❌ Sentiment analysis failed: {str(e)[:50]}...")
                    print(f"      🔄 Using default disagreement score of 50%")
                    formatted_article['disagreement_score'] = 50
                    formatted_article['sentiment_analysis'] = {
                        'disagreement_score': 50,
                        'sentiment_original': 'neutral',
                        'sentiment_related': 'neutral',
                        'disagreement_level': 'medium',
                        'confidence': 0,
                        'analysis_summary': 'Analysis failed',
                        'reason': f'Sentiment analysis failed: {str(e)[:100]}'
                    }
            else:
                formatted_article['disagreement_score'] = 50
            
            formatted_related_articles.append(formatted_article)
        
        # Sort by disagreement score for AI comparison
        formatted_related_articles.sort(key=lambda x: x.get('disagreement_score', 50), reverse=True)
        print(f"   📊 Articles sorted by disagreement for AI comparison")
        
        # Use existing generate_comparative_summary function
        comparative_summary = generate_comparative_summary(
            original_article, 
            formatted_related_articles[:5]  # Limit to top 5 for better analysis and faster processing
        )
        
        if comparative_summary:
            print(f"✅ AI comparison completed successfully!")
            return JsonResponse({
                'success': True,
                'comparison': comparative_summary
            })
        else:
            print(f"⚠️ AI comparison returned empty result")
            # Return a basic analysis instead of failing
            basic_analysis = {
                'articles_analyzed': len(related_articles),
                'summary': f"Analysis of {len(related_articles)} related articles about '{article_title}' shows various perspectives and coverage approaches. The articles span different sources and time periods, providing a comprehensive view of the topic.",
                'sections': {
                    'Coverage Summary': f"Found {len(related_articles)} related articles from various sources",
                    'Source Analysis': f"Articles from: {', '.join(set([a.get('source_id', 'Unknown') for a in formatted_related_articles[:5]]))}",
                    'Content Overview': "Articles show varying depth of coverage and perspective on the topic"
                },
                'highest_disagreement_score': 0
            }
            return JsonResponse({
                'success': True,
                'comparison': basic_analysis
            })
            
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        print(f"❌ Error in AI comparison: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Return error with some context
        return JsonResponse({
            'success': False,
            'error': f'Analysis failed: {str(e)}. Please try again.'
        }, status=500)

# Image news analyzer
def analyze_ocr_text(ocr_text, manual_publish_date=None):
    """Analyze OCR extracted text (headlines/snippets) and find related news"""
    print(f"\n🔍 Starting OCR text analysis...")
    print(f"📝 OCR text: {ocr_text[:200]}...")
    
    try:
        # Extract keywords from OCR text
        print(f"🏷️ Extracting keywords from OCR text...")
        keywords = get_keywords(ocr_text)
        keywords_list = keywords if isinstance(keywords, list) else [str(keywords)]
        print(f"🔑 Keywords extracted: {keywords_list}")
        
        # Use manual date if provided, otherwise use current date
        target_date = None
        if manual_publish_date:
            try:
                target_date = datetime.strptime(manual_publish_date, '%Y-%m-%d')
                print(f"📅 Using manual date: {target_date}")
            except ValueError:
                target_date = datetime.now()
                print(f"⚠️ Invalid date format, using today: {target_date}")
        else:
            target_date = datetime.now()
            print(f"📅 Using current date: {target_date}")
        
        # Find related news (no sentiment analysis since we lack full original content)
        print(f"🔗 Finding related news for OCR content...")
        related_news = find_related_news(
            keywords_list, 
            target_date, 
            original_url=None,  # No original URL for OCR
            original_text=None,  # No full text for sentiment analysis
            limit=10
        )
        
        # Generate summary of related articles instead of sentiment comparison
        print(f"📄 Generating content summary for {len(related_news)} articles...")
        content_summary = generate_ocr_content_summary(ocr_text, related_news, keywords_list)
        
        print(f"✅ OCR analysis completed!")
        print(f"📊 Results: {len(related_news)} related articles found")
        
        return {
            'ocr_text': ocr_text,
            'keywords': keywords_list[:10],
            'target_date': target_date,
            'manual_date_used': manual_publish_date is not None,
            'related_news': related_news,
            'content_summary': content_summary,
            'analysis_type': 'OCR_CONTENT_SUMMARY',
            'search_info': {
                'target_date': target_date.strftime('%Y-%m-%d'),
                'keywords_used': keywords_list[:6],
                'total_found': len(related_news),
                'analysis_method': 'OCR headline analysis + content summary',
                'sorting_method': 'Similarity + Recency (no sentiment analysis)',
                'limitation': 'Limited to headline analysis - full article sentiment comparison not available'
            }
        }
        
    except Exception as e:
        print(f"❌ Error in OCR analysis: {e}")
        return {
            'ocr_text': ocr_text,
            'keywords': [],
            'target_date': None,
            'related_news': [],
            'content_summary': None,
            'error': str(e),
            'analysis_type': 'OCR_ERROR'
        }

def generate_ocr_content_summary(ocr_text, related_articles, keywords):
    """Generate content summary for OCR analysis since we can't do sentiment comparison"""
    
    print(f"\n📝 Generating OCR content summary...")
    print(f"📰 OCR text: {ocr_text[:100]}...")
    print(f"📊 Related articles: {len(related_articles)}")
    
    if not related_articles:
        return {
            'summary': 'No related articles found to summarize.',
            'content_analysis': 'Unable to provide content analysis - no related articles available.',
            'coverage_overview': 'No coverage found for this topic.'
        }
    
    # Get content from top related articles
    articles_content = f"ORIGINAL OCR TEXT (from social media/image):\n{ocr_text}\n\n"
    articles_content += f"SEARCH KEYWORDS USED: {', '.join(keywords[:5])}\n\n"
    
    # Fetch content from top 5 related articles
    for i, article in enumerate(related_articles[:5], 1):
        title = article.get('title', f'Article {i}')
        similarity_score = article.get('similarity_score', 0)
        source = article.get('source_id', 'Unknown')
        pub_date = article.get('pubDate', 'Unknown date')
        
        # Try to get article content
        article_content = ""
        article_url = article.get('link')
        if article_url:
            try:
                print(f"  📰 Fetching content for article {i}: {title[:40]}...")
                news_article = Article(article_url)
                news_article.download()
                news_article.parse()
                article_content = news_article.text[:1500] if news_article.text else ""
                print(f"    ✅ Content fetched: {len(article_content)} chars")
            except Exception as e:
                print(f"    ❌ Failed to fetch content: {str(e)[:30]}...")
                article_content = f"{article.get('description', 'No description available')}"
        else:
            article_content = f"{article.get('description', 'No description available')}"
        
        articles_content += f"RELATED ARTICLE {i} (Similarity: {similarity_score}):\n"
        articles_content += f"Title: {title}\n"
        articles_content += f"Source: {source}\n"
        articles_content += f"Date: {pub_date}\n"
        articles_content += f"Content: {article_content}...\n\n"
    
    # Create prompt for content summary (not sentiment comparison)
    prompt = f"""
    You are analyzing a headline/text extracted from social media (OCR) and related news articles found about the same topic.
    Since this is OCR from social media, we don't have the full original article content, so focus on content summary rather than sentiment comparison.
    
    {articles_content}
    
    Please provide a comprehensive analysis in the following structure:

    1. TOPIC ANALYSIS: What topic/event is this OCR text referring to based on the related articles found?
    
    2. RELATED COVERAGE: Summary of how different news sources are covering this topic
    
    3. KEY INFORMATION: The most important facts and details found across the related articles
    
    4. SOURCE DIVERSITY: Analysis of the variety of sources covering this topic
    
    5. CONTENT VERIFICATION: Based on the related articles, does the OCR text appear to be about a legitimate news topic?
    
    6. SUMMARY: Overall summary of what we learned about this topic from the related articles

    Keep the analysis factual and informative. Focus on providing context and information rather than opinion comparison.
    Format your response in clear sections as requested above.
    """
    
    try:
        print(f"🤖 Sending to ChatGPT for content summary...")
        print(f"📏 Content length: {len(articles_content)} characters")
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2000
        )
        
        summary_text = response.choices[0].message.content.strip()
        print(f"✅ Content summary generated successfully")
        print(f"📄 Summary length: {len(summary_text)} characters")
        
        # Parse sections like in the sentiment analysis
        sections = {}
        current_section = None
        current_content = []
        
        for line in summary_text.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            # Check for section headers
            if any(header in line.upper() for header in ['TOPIC ANALYSIS', 'RELATED COVERAGE', 'KEY INFORMATION', 'SOURCE DIVERSITY', 'CONTENT VERIFICATION', 'SUMMARY']):
                # Save previous section
                if current_section and current_content:
                    sections[current_section] = '\n'.join(current_content)
                
                # Start new section
                current_section = line.replace(':', '').strip()
                current_content = []
            else:
                if current_section:
                    current_content.append(line)
        
        # Save last section
        if current_section and current_content:
            sections[current_section] = '\n'.join(current_content)
        
        return {
            'full_summary': summary_text,
            'sections': sections,
            'articles_analyzed': len(related_articles[:5]),
            'analysis_type': 'CONTENT_SUMMARY'
        }
        
    except Exception as e:
        print(f"❌ Error generating content summary: {str(e)}")
        return {
            'full_summary': f'Error generating summary: {str(e)}',
            'sections': {},
            'articles_analyzed': 0,
            'analysis_type': 'SUMMARY_ERROR'
        }

@csrf_exempt 
def analyze_ocr_api(request):
    """API endpoint for OCR text analysis"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)
    
    try:
        data = json.loads(request.body)
        ocr_text = data.get('ocr_text', '').strip()
        publish_date = data.get('publish_date', '')
        
        print(f"\n🌐 OCR API Request received:")
        print(f"   📝 OCR text: {ocr_text[:100]}...")
        print(f"   📅 Manual date: {publish_date if publish_date else 'Not provided'}")
        
        if not ocr_text:
            return JsonResponse({
                'success': False,
                'error': 'No OCR text provided'
            }, status=400)
        
        # Analyze OCR text
        print(f"🚀 Starting OCR analysis...")
        analysis_result = analyze_ocr_text(ocr_text, publish_date if publish_date else None)
        
        print(f"✅ OCR analysis completed")
        return JsonResponse({
            'success': True,
            'analysis': analysis_result
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        print(f"❌ Error in OCR analysis API: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'OCR analysis failed: {str(e)}'
        }, status=500)

def extract_headline_from_image(image_file):
    """Extract headline from image using OpenAI Vision API"""
    print(f"\n👁️ Starting image headline extraction with OpenAI Vision...")
    
    try:
        # Convert image to base64
        import base64
        import io
        from PIL import Image
        
        # Open and process image
        image = Image.open(image_file)
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Resize if too large (OpenAI has size limits)
        max_size = 1024
        if max(image.size) > max_size:
            ratio = max_size / max(image.size)
            new_size = tuple(int(dim * ratio) for dim in image.size)
            image = image.resize(new_size, Image.Resampling.LANCZOS)
            print(f"📏 Resized image to: {new_size}")
        
        # Convert to base64
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=85)
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        print(f"🖼️ Image processed, size: {len(image_base64)} characters")
        
        # Create prompt for headline extraction
        prompt = """
        You are analyzing an image that contains news headlines, likely from social media (Instagram, Facebook, Twitter, etc.) or news websites.
        
        Please:
        1. Extract the main headline/news text from this image
        2. Focus on the primary news content, ignore usernames, timestamps, reaction counts, etc.
        3. If there are multiple headlines, prioritize the largest/most prominent one
        4. Preserve the original language (English, Indonesian, etc.)
        5. Return ONLY the headline text, no additional commentary
        
        Response rules:
        - If you find a clear, readable news headline: Return ONLY the headline text
        - If the image contains random characters, gibberish, or unreadable text: Respond with "GIBBERISH"
        - If no clear headline is visible: Respond with "NO_HEADLINE_FOUND"

        
        Examples:
        Good: "Breaking: Indonesia announces new economic policy"
        Good: "Presiden Jokowi resmikan jalan tol baru"
        Bad: "adjdiwnfeuvb" → Return "GIBBERISH"
        Bad: "cakaladut" → Return "GIBBERISH"
        Bad: Blurry/unclear text → Return "NO_HEADLINE_FOUND"
        """
        
        # Send to OpenAI Vision API
        print(f"🤖 Sending to OpenAI Vision API...")
        response = client.chat.completions.create(
            model="gpt-4o",  # GPT-4 with vision
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            max_tokens=500,
            temperature=0.1  # Low temperature for more accurate extraction
        )
        
        extracted_text = response.choices[0].message.content.strip()
        
        print(f"✅ Headline extracted successfully:")
        print(f"📰 Result: {extracted_text}")
        
        if extracted_text == "NO_HEADLINE_FOUND":
            return {
                'success': False,
                'error': 'No clear headline found in the image',
                'extracted_text': None,
                'validation_error': 'NO_HEADLINE_FOUND'
            }
        
        elif extracted_text == "GIBBERISH":
            return {
                'success': False,
                'error': 'The extracted text appears to be random characters or unreadable content, not a recognizable news headline.',
                'extracted_text': extracted_text,
                'validation_error': 'GIBBERISH'
            }
        
        else:
            return {
                'success': True,
                'extracted_text': extracted_text,
                'method': 'OpenAI Vision API',
                'confidence': 'high'
            }
        
    except Exception as e:
        print(f"❌ Error in OpenAI Vision extraction: {str(e)}")
        return {
            'success': False,
            'error': f'Vision API failed: {str(e)}',
            'extracted_text': None
        }

def analyze_image_headline(image_file, manual_publish_date=None):
    """Complete image analysis using OpenAI Vision + news analysis"""
    print(f"\n🚀 Starting complete image headline analysis...")
    
    # Step 1: Extract headline using Vision API
    extraction_result = extract_headline_from_image(image_file)
    
    if not extraction_result['success']:

        validation_error = extraction_result.get('validation_error', 'IMAGE_EXTRACTION_ERROR')
        
        if validation_error == 'GIBBERISH':
            return {
                'extraction_error': extraction_result['error'],
                'analysis_type': 'TEXT_VALIDATION_ERROR',
                'validation_reason': 'INVALID_GIBBERISH',
                'extracted_text': extraction_result.get('extracted_text')
            }
        else:
            return {
                'extraction_error': extraction_result['error'],
                'analysis_type': 'IMAGE_EXTRACTION_ERROR'
            }
    
    headline_text = extraction_result['extracted_text']
    print(f"📰 Extracted headline: {headline_text}")
    
    # Step 2: Analyze the extracted headline (same as OCR analysis)
    print(f"🔍 Starting news analysis for extracted headline...")
    analysis_result = analyze_ocr_text(headline_text, manual_publish_date)
    
    # Step 3: Check if any related articles were found
    if not analysis_result.get('related_news') or len(analysis_result.get('related_news', [])) == 0:
        print(f"❌ No related articles found for the extracted headline")
        return {
            'extraction_error': f'No related news articles found for: "{headline_text}". The text may be too specific, outdated, or not covered by major news sources.',
            'analysis_type': 'NO_ARTICLES_FOUND',
            'extracted_text': headline_text,
            'keywords_used': analysis_result.get('keywords', [])
        }
    
    # Add extraction info to the result
    analysis_result['extraction_method'] = 'OpenAI Vision API'
    analysis_result['extraction_confidence'] = 'high'
    analysis_result['original_image_processed'] = True
    analysis_result['text_validated'] = True
    
    return analysis_result