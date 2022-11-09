import time, random, requests, threading
from asyncio import Queue
from bs4 import BeautifulSoup
import alive_progress
import csv

def refinde(str):
    s = str.replace('\xa0', ' ')
    return s.replace('&nbsp;', ' ')


def generate_urls(url, LINKS: Queue):
    print('Генерируем список страниц со статьями')
    for i in range(17, 0, -1):
        link: str = url + 'page' + str(i) + '_1079.htm'
        LINKS.put_nowait(link)
    print('Генерация завершена')


def get_html(link):
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; rv:91.0) Gecko/20100101 Firefox/91.0",
        "Mozilla/5.0 (Windows NT 10.0; rv:78.0) Gecko/20100101 Firefox/78.0",
        "Mozilla/5.0 (X11; Linux x86_64; rv:95.0) Gecko/20100101 Firefox/95.0"
    ]
    random_user_agent = random.choice(user_agents)
    headers = {
            'User-Agent': random_user_agent
        }
    response = requests.get(link, headers=headers)
    if response.status_code == 200:
        return response.text 
    
    return 404
    
    
def get_article_link(articles, PAGES_WITH_ARTICLES: Queue):
    for article in articles:
        link = 'http://www.pravoslavie.ru' + article.find('a').get('href')
        PAGES_WITH_ARTICLES.put_nowait(link)


def get_pages_with_articles(LINKS: Queue, PAGES_WITH_ARTICLES: Queue):
    count = LINKS.qsize()
    with alive_progress.alive_bar(count) as bar:
        print('Получаем сслыки на статьи')
        for i in range(count):
            while LINKS.empty():
                time.sleep(0.5)
            link = LINKS.get_nowait()
            html = get_html(link)
            if html == 404:
                continue
            soup = BeautifulSoup(html, 'lxml')
            articles = soup.find('div', class_='list_articles').find_all('div', class_='item')
            get_article_link(articles, PAGES_WITH_ARTICLES)
            bar()


def dowload_articles(link, ARTICLE_HTML: Queue):
    html = get_html(link)
    if html != 404:
        ARTICLE_HTML.put_nowait({
            'link': link,
            'html': html
            })

def get_article_data(num, data, ARTICLE_DATA: Queue):
    soup = BeautifulSoup(data['html'], 'lxml')
    article_title = None
    article_author = None
    article_published = None
    article_rating = None
    article_comment_count = None
    if soup.find('h1', class_='block-doc__title') is not None:
        article_title = soup.find('h1', class_='block-doc__title').text
    if soup.find('p', class_='block-doc__author') is not None and soup.find('p', class_='block-doc__author').find('a') is not None:
        article_author = soup.find('p', class_='block-doc__author').find('a').text
    if soup.find('p', class_='block-doc__date') is not None:
        article_published = refinde(soup.find('p', class_='block-doc__date').text)
    """ article_rating = soup.find('div', class_='block-rating').find_all('span', class_='block-rating__overall') """
    if soup.find_all('div', class_='block-comments__item') is not None:
        article_comment_count = len(soup.find_all('div', class_='block-comments__item'))
    
    ARTICLE_DATA.put_nowait({
        'number': num,
        'link': data['link'],
        'title': article_title,
        'author': article_author,
        'date': article_published,
        'rating': article_rating,
        'comment-count': article_comment_count
    })


def get_data(ARTICLE_HTML: Queue, ARTICLE_DATA: Queue):
    print('Собираем данные')
    with alive_progress.alive_bar(ARTICLE_HTML.qsize()) as bar:
        for i in range(ARTICLE_HTML.qsize()):
            while ARTICLE_HTML.empty():
                time.sleep(0.2)
            get_article_data(i+1, ARTICLE_HTML.get_nowait(), ARTICLE_DATA)
            bar()


def loading(PAGES_WITH_ARTICLES: Queue, ARTICLE_HTML: Queue):
    print('Загрузка')
    with alive_progress.alive_bar(PAGES_WITH_ARTICLES.qsize()) as bar:
        for i in range(PAGES_WITH_ARTICLES.qsize()):
            while PAGES_WITH_ARTICLES.empty():
                time.sleep(0.2)
            if i != 0 and i % 100 == 0:
                time.sleep(10)
            link = PAGES_WITH_ARTICLES.get_nowait()
            dowload_articles(link, ARTICLE_HTML)
            time.sleep(0.5)
            bar()


def main():
    url = 'https://pravoslavie.ru/put/' # основная ссылка
    
    LINKS = Queue() # список ссылок для получения списка статей
    PAGES_WITH_ARTICLES = Queue() # список ссылок статей
    ARTICLE_HTML = Queue() # загруженные страницы
    ARTICLE_DATA = Queue() # список данных

    generate_urls(url, LINKS)
    thread_get_link_article = threading.Thread(
        target=get_pages_with_articles, args=(LINKS, PAGES_WITH_ARTICLES))
    thread_get_link_article.run()
    
    thread_loading = threading.Thread(
        target=loading, args=(PAGES_WITH_ARTICLES, ARTICLE_HTML))
    thread_loading.run()

    thread_data = threading.Thread(
        target=get_data, args=(ARTICLE_HTML, ARTICLE_DATA))
    thread_data.run()
    
    with open('./output/dump.csv', 'a', newline='') as f:
        print('Запись в файл')
        recorder = csv.writer(f, delimiter=',')
        recorder.writerow((
            "#",
            "Заголовок",
            "Автор",
            "Дата публикации",
            "рейтинг статьи",
            "Кол-во комментариев",
            "Ссылка на статью"
        ))
        for i in range(ARTICLE_DATA.qsize()):
            line = ARTICLE_DATA.get_nowait()
            recorder.writerow((
                line['number'],
                line['title'],
                line['author'],
                line['date'],
                line['rating'],
                line['comment-count'],
                line['link']
            ))


if __name__ == "__main__":
    main()