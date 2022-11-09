import threading
from asyncio import Queue
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


def get_links(PAGES_WITH_ARTICLES: Queue):
    with open('./source/pravoslavie.txt', 'r') as f:
        for line in f.readlines():
            line = line.replace('\n', '')
            PAGES_WITH_ARTICLES.put_nowait(line.replace('\\n', ''))
        f.close()


def get_article_data(PAGES_WITH_ARTICLES: Queue, ARTICLE_DATA: Queue):
    print('собираем данные')
    with alive_progress.alive_bar(PAGES_WITH_ARTICLES.qsize()) as bar:
        for i in range(PAGES_WITH_ARTICLES.qsize()):
            link = PAGES_WITH_ARTICLES.get_nowait()
            load_data = Client.get_data(link)
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
    PAGES_WITH_ARTICLES = Queue() # список ссылок статей
    ARTICLE_DATA = Queue() # список данных
    
    thread_getLinks = threading.Thread(
        target=get_links, args=(PAGES_WITH_ARTICLES))

    thread_data = threading.Thread(
        target=get_article_data, args=(PAGES_WITH_ARTICLES, ARTICLE_DATA))
    
    
    thread_getLinks.run()
    thread_data.run()

    thread_getLinks.join()
    thread_data.join()

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