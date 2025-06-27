from django.shortcuts import render
from newsapi import NewsApiClient
from django.conf import settings
from easyocr import Reader
from PIL import Image
import io

from main.forms import ImageUploadForm

# Create your views here.

def show_main(request):
    text_result = None
    if request.method == 'POST':
        form = ImageUploadForm(request.POST, request.FILES)
        if form.is_valid():
            image_file = request.FILES['image']

            # Baca gambar langsung dari memori
            image = Image.open(image_file)

            # Convert ke format yang bisa dibaca easyocr
            image_bytes = io.BytesIO()
            image.save(image_bytes, format='PNG')
            image_bytes = image_bytes.getvalue()

            reader = Reader(['en'], gpu=False)
            result = reader.readtext(image_bytes, detail=0)
            text_result = "\n".join(result)
    else:
        form = ImageUploadForm()

    context = {
        'form': form,
        'text_result': text_result
    }

    return render(request, 'main.html', context)
