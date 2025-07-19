from newspaper import Article

url = "https://mediaindonesia.com/premium/197/jejak-chromebook-di-balik-digitalisasi-sekolah-dan-potensi-kerugian-negara"

article = Article(url)
article.download()
article.parse()

print(article.title)
print(article.text)

# tolong jangan lupa kita harus baca robots.txt sebelum melakukan scraping