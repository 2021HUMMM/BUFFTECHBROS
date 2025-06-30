from django.shortcuts import render
from newsapi import NewsApiClient
from django.conf import settings
from easyocr import Reader
from PIL import Image
import io
from main.forms import ImageUploadForm
import spacy
import openai

nlp = spacy.load("en_core_web_sm")

def extract_query_from_text(text):
    doc = nlp(text)

    # Ambil named entities
    entities = [ent.text for ent in doc.ents if ent.label_ in ["PERSON", "ORG", "GPE", "EVENT", "DATE"]]

    # Ambil noun phrases
    noun_phrases = [chunk.text for chunk in doc.noun_chunks]

    # Gabungkan, hindari duplikat
    phrases = list(dict.fromkeys(entities + noun_phrases))

    # Ambil maksimal 5 frasa teratas
    query_string = " ".join(phrases[:5])
    return query_string

def show_main(request):
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
        'keywords': extract_query_from_text(text_result) if text_result else None,
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