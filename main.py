import threading
from asyncio import Queue
import alive_progress
import csv, json

from selenium.webdriver.chrome.service import Service
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

from bs4 import BeautifulSoup

class Client:
    def get_data(url):
        service = Service(executable_path="./driver/chromedriver")
        options = Options()
        caps = DesiredCapabilities().CHROME
        caps['pageLoadStrategy'] = "normal"
        options.add_argument("--headless")
        driver = webdriver.Chrome(service=service, options=options, desired_capabilities=caps)
        driver.get(url)
        

        page = {
            'current-url': driver.current_url,
            'html': driver.find_element(By.TAG_NAME, 'html').get_attribute('innerHTML')
        }
        
        driver.quit()
        return page


def refinde(str):
    s = str.replace('\xa0', ' ')
    return s.replace('&nbsp;', ' ')


def get_links(PAGES_WITH_ARTICLES: Queue):
    with open('./source/pravoslavie.txt', 'r') as f:
        for line in f.readlines():
            line = line.replace('\n', '')
            PAGES_WITH_ARTICLES.put_nowait(line.replace('\\n', ''))
        f.close()


def load_pages(SOURCE: Queue, OUTPUT: Queue):
    print('Загрузка страниц')
    with alive_progress.alive_bar(SOURCE.qsize()) as bar:
        for i in range(SOURCE.qsize()):
            link = SOURCE.get_nowait()
            load_data = Client.get_data(link)
            OUTPUT.put_nowait({
                'link': link,
                'current-url': load_data['current-url'],
                'html': load_data['html']
            })
            bar()


def save_pages(SOURCE: Queue):
    print('Сохраняем')
    with open('./source/loaded-pages.json', 'a') as file:
        data: list = []
        for i in range(SOURCE.qsize()):
            data.append(SOURCE.get_nowait())
        
        json.dump(data, file, ensure_ascii=False)
        file.close()

def load_file(OUTPUT: Queue):
    with open('./source/loaded-pages.json', 'r') as file:
        data = json.loads(file.read())
        for item in data:
            OUTPUT.put_nowait(item)


def research(soup: BeautifulSoup):
    header: str = None
    subtitle: str = None 
    author = None 
    views = None 
    date_publication = None 
    rating_ball = None
    rating_count = None
    comment_count = None
    
    if soup.find('title') is not None:
        header = soup.find('title').text.replace(' / Православие.Ru', '')
    elif soup.find('h1') is not None:
        header = soup.find('h1').text
    
    if soup.find('h2', class_='block-photogallery__subheading') is not None:
        subtitle = soup.find('h2', class_='block-photogallery__subheading').text
    else:
        subtitle = 'N/A'

    if soup.find('p', class_='block-doc__author') is not None:
        author = soup.find('p', class_='block-doc__author').text
    else:
        author = 'Не указан'

    if soup.find('ul', class_='block-doc-print') is not None and \
        soup.find('ul', class_='block-doc-print').find('li') is not None:
        views = soup.find('ul', class_='block-doc-print').find('li').text
    else:
        views = 'N/A'
    
    if soup.find('p', class_='block-doc__date') is not None:
        date_publication = soup.find('p', class_='block-doc__date').text
    else:
        date_publication = 'N/A'

    if soup.find('div', 'block-rating') is not None and \
        soup.find('div', 'block-rating').find_all('span', 'block-rating__overall') is not None:
        
        rating = soup.find('div', 'block-rating').find_all('span', 'block-rating__overall')
        if len(rating) != 0:
            rating_ball = rating[0].text
            rating_count = rating[1].text
        else:
            rating_ball = 'N/A'
            rating_count = 'N/A'

    if soup.find_all('div', class_='block-comments__item') is not None:
        comment_count = len(soup.find_all('div', class_='block-comments__item'))
    else:
        comment_count = "Комментариев нет"

    return {
        'title': header,
        'subtitle': subtitle,
        'author': author,
        'date-publication': date_publication,
        'views-count': views,
        'rating': rating_ball,
        'rating-count': rating_count,
        'comment-count': comment_count
    }
    
def get_article_data(SOURCE: Queue, OUTPUT: Queue):
    print('собираем данные')
    with alive_progress.alive_bar(SOURCE.qsize()) as bar:
        for i in range(SOURCE.qsize()):
            article_data = SOURCE.get_nowait()
            soup = BeautifulSoup(article_data['html'], 'lxml')
            analyzed_data = research(soup)
            
            OUTPUT.put_nowait({
                'number': i+1,
                'source-address': article_data['link'],
                'loaded-link': article_data['current-url'],
                'title': analyzed_data['title'],
                'subtitle': analyzed_data['subtitle'],
                'author': analyzed_data['author'],
                'date': analyzed_data['date-publication'],
                'views-count': analyzed_data['views-count'],
                'rating': analyzed_data['rating'],
                'rating-count': analyzed_data['rating-count'],
                'comment-count': analyzed_data['comment-count']
            })
            bar()

def main():
    PAGES_WITH_ARTICLES = Queue() # список ссылок статей
    ARTICLE_HTML = Queue() # Список со страницами
    ARTICLE_DATA = Queue() # список данных
    
    with open('./source/pravoslavie.txt', 'r') as f:
        for line in f.readlines():
            line = line.replace('\n', '')
            PAGES_WITH_ARTICLES.put_nowait(line.replace('\\n', ''))
        f.close()


    """ load_pages(PAGES_WITH_ARTICLES, ARTICLE_HTML)
    save_pages(ARTICLE_HTML) """

    load_file(ARTICLE_HTML)
    
    get_article_data(ARTICLE_HTML, ARTICLE_DATA)

    

    with open('./output/dump.csv', 'a', newline='') as f:
        print('Запись в файл')
        recorder = csv.writer(f, delimiter=',')
        recorder.writerow((
            "#",
            "Заголовок",
            "Подзаголовок",
            "Автор",
            "Дата публикации",
            "Кол-во просмотров",
            "Рейтинг статьи",
            "Кол-во голосов",
            "Кол-во комментариев",
            "Ссылка на загружаемую статью",
            "Адрес загруженной статьи"
        ))
        for i in range(ARTICLE_DATA.qsize()):
            line = ARTICLE_DATA.get_nowait()
            recorder.writerow((
                line['number'],
                line['title'],
                line['subtitle'],
                line['author'],
                line['date'],
                line['views-count'],
                line['rating'],
                line['rating-count'],
                line['comment-count'],
                line['source-address'],
                line['loaded-link']
            ))
        f.close()


if __name__ == "__main__":
    main()
    print('Программа завершена')