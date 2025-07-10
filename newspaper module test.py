from newspaper import Article

url = "https://mediaindonesia.com/internasional/788620/wacana-membawa-kasus-juliana-ke-hukum-internasional-yusril-pemerintah-belum-terima-nota-diplomatik-dari-brasil"

article = Article(url)
article.download()
article.parse()

print(article.title)
print(article.text)

# tolong jangan lupa kita harus baca robots.txt sebelum melakukan scraping