from django.shortcuts import render, redirect
# from newsapi import NewsApiClient
from django.conf import settings
from easyocr import Reader
from PIL import Image
import io
from main.forms import ImageUploadForm
import openai
from newspaper import Article


# Page Navigator

def main_redirect(request):
    # Redirect based on authentication status
    if request.user.is_authenticated:
        return redirect('main:show_main')
    else:
        return render(request, 'landing.html')

def landing_page(request):
    return render(request, 'landing.html')


def show_main(request):
    news_article = Article("https://cenderawasihpos.jawapos.com/metropolis/22/07/2025/pastikan-program-mbg-harus-berkelanjutan/")
    news_article.download()
    news_article.parse()

    print(f"     📰 Title: {news_article.title}"
          f"\n     📰 Text: {news_article.text[:100]}")


    text_result = None
    if request.method == 'POST':
        form = ImageUploadForm(request.POST, request.FILES)
        if form.is_valid():
            image_file = request.FILES['image']

            # Baca gambar langsung dari memori
            image = Image.open(image_file)
            try:
                image_bytes = io.BytesIO()
                image.save(image_bytes, format='PNG')
                image_bytes = image_bytes.getvalue()

                reader = Reader(['en'], gpu=False)
                result = reader.readtext(image_bytes, detail=0)
                text_result = "\n".join(result)
            finally:
                image.close()
    else:
        form = ImageUploadForm()

    context = {
        'form': form,
        'text_result': text_result,
    }

    return render(request, 'main.html', context)

openai.api_key = settings.OPENAI_API_KEY

client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

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