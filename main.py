import time, random, requests, threading
from asyncio import Queue
from bs4 import BeautifulSoup
import alive_progress
import csv

from selenium.webdriver.chrome.service import Service
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

class Client:
    def get_data(url):
        service = Service(executable_path="./driver/chromedriver")
        options = Options()
        options.add_argument("--headless")
        caps = DesiredCapabilities()
        caps['pageLoadStrategy'] = 'eager'
        driver = webdriver.Chrome(service=service, options=options, desired_capabilities=caps)
        driver.get(url)

        try:
            h1_title = driver.find_element(By.CLASS_NAME, 'block-doc__title').text
            author = driver.find_element(By.CLASS_NAME, "block-doc__author").find_element(By.TAG_NAME, 'a').text
            article_published = refinde(driver.find_element(By.CLASS_NAME, 'block-doc__date').text)
            article_rating = driver.find_element(By.CLASS_NAME, 'block-rating').find_elements(By.CLASS_NAME, 'block-rating__overall')
            article_comment_count = len(driver.find_elements(By.CLASS_NAME, 'block-comments__item'))
            data = {
                'title': h1_title,
                'author': author,
                'published': article_published,
                'rating': article_rating[0].text,
                'rating-count': article_rating[1].text,
                'comment-count': article_comment_count
            }
        except IndexError:
            h1_title = driver.find_element(By.CLASS_NAME, 'block-doc__title').text
            author = driver.find_element(By.CLASS_NAME, "block-doc__author").find_element(By.TAG_NAME, 'a').text
            article_published = refinde(driver.find_element(By.CLASS_NAME, 'block-doc__date').text)
            article_comment_count = len(driver.find_elements(By.CLASS_NAME, 'block-comments__item'))
            data = {
                'title': 'errData',
                'author': 'errData',
                'published': 'errData',
                'rating': 'N/A',
                'rating-count': 'N/A',
                'comment-count': 'errData'
            }
        except NoSuchElementException:
            data = {
                'title': 'none',
                'author': 'none',
                'published': 'none',
                'rating': 'none',
                'rating-count': 'none',
                'comment-count': 'none'
            }
        
        driver.quit()
        return data


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


def download_article_selenium(link):
    return Client.get_data(link)


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


def get_data(ARTICLE_HTML: Queue, ARTICLE_DATA: Queue):
    print('Собираем данные')
    with alive_progress.alive_bar(ARTICLE_HTML.qsize()) as bar:
        for i in range(ARTICLE_HTML.qsize()):
            while ARTICLE_HTML.empty():
                time.sleep(0.2)
            get_article_data(i+1, ARTICLE_HTML.get_nowait(), ARTICLE_DATA)
            bar()


def get_article_data(PAGES_WITH_ARTICLES: Queue, ARTICLE_DATA: Queue):
    print('собираем данные')
    with alive_progress.alive_bar(PAGES_WITH_ARTICLES.qsize()) as bar:
        for i in range(PAGES_WITH_ARTICLES.qsize()):
            link = PAGES_WITH_ARTICLES.get_nowait()
            load_data = download_article_selenium(link)
            ARTICLE_DATA.put_nowait({
                'number': i+1,
                'link': link,
                'title': load_data['title'],
                'author': load_data['author'],
                'date': load_data['published'],
                'rating': load_data['rating'],
                'rating-count': load_data['rating-count'],
                'comment-count': load_data['comment-count']
            })
            bar()

def main():
    url = 'https://pravoslavie.ru/put/' # основная ссылка
    
    LINKS = Queue() # список ссылок для получения списка статей
    PAGES_WITH_ARTICLES = Queue() # список ссылок статей
    ARTICLE_HTML = Queue() # загруженные страницы
    ARTICLE_DATA = Queue() # список данных

    """ generate_urls(url, LINKS)
    thread_get_link_article = threading.Thread(
        target=get_pages_with_articles, args=(LINKS, PAGES_WITH_ARTICLES))
    thread_get_link_article.run() """
    
    """ thread_loading = threading.Thread(
        target=loading, args=(PAGES_WITH_ARTICLES, ARTICLE_HTML))
    thread_loading.run() """
    with open('./source/pravoslavie.txt', 'r') as f:
        for line in f.readlines():
            line = line.replace('\n', '')
            PAGES_WITH_ARTICLES.put_nowait(line.replace('\\n', ''))
        f.close()
    thread_data = threading.Thread(
        target=get_article_data, args=(PAGES_WITH_ARTICLES, ARTICLE_DATA))
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
            "Кол-во голосов",
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
                line['rating-count'],
                line['comment-count'],
                line['link']
            ))


if __name__ == "__main__":
    main()