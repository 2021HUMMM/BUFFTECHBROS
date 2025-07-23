from django.shortcuts import render, redirect
from django.conf import settings
from easyocr import Reader
from PIL import Image
from main.forms import ImageUploadForm
from newspaper import Article
from analyzer.views import analyze_image_headline

import io
import openai

# API Keys
openai.api_key = settings.OPENAI_API_KEY
client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

# Page Navigator
def main_page(request):
    # Redirect based on authentication status
    return render(request, 'landing.html')

def show_main(request):
    text_result = None
    image_analysis = None
    
    if request.method == 'POST':
        form = ImageUploadForm(request.POST, request.FILES)
        if form.is_valid():
            image_file = request.FILES['image']
            publish_date = request.POST.get('publish_date', '')
            
            print(f"🖼️ Processing uploaded image with OpenAI Vision...")
            
            try:
                # Use OpenAI Vision API for complete analysis
                image_analysis = analyze_image_headline(image_file, publish_date if publish_date else None)
                
                # Extract text for display (backward compatibility)
                if image_analysis and 'ocr_text' in image_analysis:
                    text_result = image_analysis['ocr_text']
                    print(f"✅ Image analysis completed successfully")
                else:
                    print(f"⚠️ Image analysis completed but no headline found")
                    
            except Exception as e:
                print(f"❌ Error in image analysis: {str(e)}")
                image_analysis = {
                    'analysis_type': 'IMAGE_ERROR',
                    'error': str(e)
                }
    else:
        form = ImageUploadForm()

    context = {
        'form': form,
        'text_result': text_result,
        'image_analysis': image_analysis,  # New: complete analysis result
        'ocr_analysis': image_analysis,    # Backward compatibility
    }

    return render(request, 'main.html', context)

def test_chat(request):
    reply = None
    user_input = None

    if request.method == 'POST':
        user_input = request.POST.get('message')
        if user_input:
            response = client.chat.completions.create(
                model="gpt-4o",  # atau "gpt-3.5-turbo"
                messages=[
                    {"role": "user", "content": user_input}
                ]
            )
            reply = response.choices[0].message.content

    return render(request, 'test_chat.html', {
        'user_input': user_input,
        'reply': reply
    })