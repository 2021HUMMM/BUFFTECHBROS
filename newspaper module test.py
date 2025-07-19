from newspaper import Article

url = "https://sport.detik.com/sepakbola/liga-indonesia/d-8018540/pssi-dorong-pembangunan-ekosistem-pelatih-sepakbola"

article = Article(url)
article.download()
article.parse()

print(article.title)
print(article.text)

# tolong jangan lupa kita harus baca robots.txt sebelum melakukan scraping