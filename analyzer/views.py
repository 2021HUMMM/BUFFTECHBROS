from django.conf import settings
from django.shortcuts import render
import openai
# Create your views here.

openai.api_key = settings.OPENAI_API_KEY

client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)


def get_keywords(page_string):
    reply = None
    user_input = """Here's a news article. i want you to extract the keywords from it to a csv string format.
                    adapt to its original language, if it's in indonesian, return it in indonesian, if it's 
                    in english, return it in english. the goal is to extract the most relevant keywords that 
                    represent the content of the article for me to then forward it to a news api to find similar news.
                    
                    heres an example of the result im hoping you to return: 'keyword1, keyword2, keyword3'

                    do not return any other text, just the keywords in csv string format, not a csv file.
                    
                    here's the article:\n{}""".format(page_string)
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "user", "content": user_input}
        ]
    )
    reply = str(response.choices[0].message.content.strip())
    reply = reply.split(',')  # Split the reply into a list of keywords

    return reply


    


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
    