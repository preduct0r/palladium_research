"""
Модуль для поиска научных статей через OpenAlex API

Этот модуль предоставляет функции для поиска научных статей по названию
и получения ссылок на PDF файлы или DOI. Использует библиотеку pyalex
для взаимодействия с OpenAlex API.

Основные функции:
- search_article_link: Поиск одной статьи по названию
- search_multiple_articles: Поиск нескольких статей
- search_by_exact_title: Поиск по точному названию
- get_article_info: Упрощенная функция для быстрого получения ссылки

Примеры использования:
    >>> link = get_article_info("Machine learning in medicine")
    >>> print(link)
    'https://europepmc.org/articles/pmc5831252?pdf=render'
    
    >>> info = search_article_link("Deep learning")
    >>> print(info['pdf_url'] or info['doi_url'])

Автор: Создано для проекта исследования палладия
"""

from pyalex import Works
import logging
from typing import Optional, Dict, Any, List, Union

def search_article_link(title: str) -> Optional[Dict[str, Any]]:
    """
    Поиск ссылки на PDF или DOI статьи по названию через OpenAlex API
    
    Args:
        title (str): Название статьи для поиска
        
    Returns:
        Optional[Dict[str, Any]]: Словарь с информацией о статье, включая:
            - pdf_url: Ссылка на PDF (если доступна)
            - doi_url: Ссылка на DOI (если PDF недоступен)
            - title: Название статьи
            - authors: Список авторов
            - publication_year: Год публикации
            - is_open_access: Статус открытого доступа
            
    Returns None если статья не найдена
    """
    try:
        # Поиск статьи по названию
        results = Works().search(title).get()
        
        if not results:
            logging.warning(f"Статья с названием '{title}' не найдена")
            return None
            
        # Берем первый результат как наиболее релевантный
        article = results[0]
        
        # Извлекаем информацию о статье
        article_info = {
            'title': article.get('title', 'Название не указано'),
            'authors': [author.get('author', {}).get('display_name', 'Неизвестный автор') 
                       for author in article.get('authorships', [])],
            'publication_year': article.get('publication_year'),
            'is_open_access': article.get('open_access', {}).get('is_oa', False),
            'pdf_url': None,
            'doi_url': None
        }
        
        # Поиск PDF ссылки
        open_access_info = article.get('open_access', {})
        if open_access_info.get('is_oa') and open_access_info.get('oa_url'):
            article_info['pdf_url'] = open_access_info['oa_url']
            logging.info(f"Найдена PDF ссылка: {article_info['pdf_url']}")
        else:
            # Проверяем другие источники для PDF
            locations = article.get('locations', [])
            for location in locations:
                if location.get('pdf_url'):
                    article_info['pdf_url'] = location['pdf_url']
                    logging.info(f"Найдена PDF ссылка в источниках: {article_info['pdf_url']}")
                    break
        
        # Если PDF не найден, ищем DOI
        if not article_info['pdf_url']:
            doi = article.get('doi')
            if doi:
                article_info['doi_url'] = doi
                logging.info(f"PDF не найден, используем DOI: {article_info['doi_url']}")
            else:
                # Альтернативный способ получения URL
                openalex_url = article.get('id')
                if openalex_url:
                    article_info['doi_url'] = openalex_url
                    logging.info(f"DOI не найден, используем OpenAlex URL: {article_info['doi_url']}")
        
        return article_info
        
    except Exception as e:
        logging.error(f"Ошибка при поиске статьи '{title}': {str(e)}")
        return None

def search_multiple_articles(title: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Расширенный поиск нескольких статей по названию
    
    Args:
        title (str): Название статьи для поиска
        max_results (int): Максимальное количество результатов
        
    Returns:
        List[Dict[str, Any]]: Список статей с информацией о ссылках
    """
    try:
        results = Works().search(title).get()
        
        if not results:
            logging.warning(f"Статьи с названием '{title}' не найдены")
            return []
        
        articles = []
        for i, article in enumerate(results[:max_results]):
            article_info = {
                'rank': i + 1,
                'title': article.get('title', 'Название не указано'),
                'authors': [author.get('author', {}).get('display_name', 'Неизвестный автор') 
                           for author in article.get('authorships', [])],
                'publication_year': article.get('publication_year'),
                'is_open_access': article.get('open_access', {}).get('is_oa', False),
                'cited_by_count': article.get('cited_by_count', 0),
                'pdf_url': None,
                'doi_url': None
            }
            
            # Поиск PDF ссылки
            open_access_info = article.get('open_access', {})
            if open_access_info.get('is_oa') and open_access_info.get('oa_url'):
                article_info['pdf_url'] = open_access_info['oa_url']
            else:
                # Проверяем другие источники для PDF
                locations = article.get('locations', [])
                for location in locations:
                    if location.get('pdf_url'):
                        article_info['pdf_url'] = location['pdf_url']
                        break
            
            # Если PDF не найден, ищем DOI
            if not article_info['pdf_url']:
                doi = article.get('doi')
                if doi:
                    article_info['doi_url'] = doi
                else:
                    openalex_url = article.get('id')
                    if openalex_url:
                        article_info['doi_url'] = openalex_url
            
            articles.append(article_info)
        
        return articles
        
    except Exception as e:
        logging.error(f"Ошибка при поиске статей '{title}': {str(e)}")
        return []

def search_by_exact_title(title: str) -> Optional[Dict[str, Any]]:
    """
    Поиск статьи по точному названию
    
    Args:
        title (str): Точное название статьи
        
    Returns:
        Optional[Dict[str, Any]]: Информация о статье или None
    """
    try:
        # Используем фильтр по точному названию
        results = Works().filter(title=title).get()
        
        if not results:
            # Пытаемся альтернативный поиск
            results = Works().search(f'"{title}"').get()
        
        if not results:
            logging.warning(f"Статья с точным названием '{title}' не найдена")
            return None
        
        return search_article_link(title)
        
    except Exception as e:
        logging.error(f"Ошибка при точном поиске статьи '{title}': {str(e)}")
        return None

def get_article_info(title: str, prefer_pdf: bool = True) -> Optional[str]:
    """
    Упрощенная функция для получения ссылки на статью
    
    Args:
        title (str): Название статьи
        prefer_pdf (bool): Предпочитать PDF ссылку перед DOI
        
    Returns:
        Optional[str]: Ссылка на PDF или DOI, или None если не найдено
        
    Example:
        >>> link = get_article_info("Machine learning in medicine")
        >>> print(link)
        'https://europepmc.org/articles/pmc5831252?pdf=render'
    """
    result = search_article_link(title)
    if not result:
        return None
    
    if prefer_pdf and result.get('pdf_url'):
        return result['pdf_url']
    elif result.get('doi_url'):
        return result['doi_url']
    elif result.get('pdf_url'):
        return result['pdf_url']
    else:
        return None

def search_articles_by_keywords(keywords: List[str], max_results: int = 10) -> List[Dict[str, Any]]:
    """
    Поиск статей по ключевым словам
    
    Args:
        keywords (List[str]): Список ключевых слов для поиска
        max_results (int): Максимальное количество результатов
        
    Returns:
        List[Dict[str, Any]]: Список найденных статей
    """
    search_query = " ".join(keywords)
    return search_multiple_articles(search_query, max_results)

def main():
    """
    Пример использования функций поиска статей
    """
    # Настройка логирования
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Пример 1: Простой поиск статьи
    print("=== Пример 1: Простой поиск ===")
    article_title = "The Effect of Addition of ppm-Order Pd to Fe-K Catalyst on Dehydrogenation of Ethylbenzene"
    print(f"Поиск статьи: '{article_title}'")
    result = search_article_link(article_title)
    
    if result:
        print(f"Название: {result['title']}")
        print(f"Авторы: {', '.join(result['authors'][:3])}{'...' if len(result['authors']) > 3 else ''}")
        print(f"Год публикации: {result['publication_year']}")
        print(f"Открытый доступ: {'Да' if result['is_open_access'] else 'Нет'}")
        
        if result['pdf_url']:
            print(f"PDF ссылка: {result['pdf_url']}")
        elif result['doi_url']:
            print(f"DOI ссылка: {result['doi_url']}")
        else:
            print("Ссылка на статью не найдена")
    else:
        print("Статья не найдена")
    
    # Пример 2: Поиск нескольких статей
    print("\n=== Пример 2: Поиск нескольких статей ===")
    search_term = "artificial intelligence"
    print(f"Поиск статей по теме: '{search_term}'")
    multiple_results = search_multiple_articles(search_term, max_results=3)
    
    for article in multiple_results:
        print(f"\n{article['rank']}. {article['title']}")
        print(f"   Год: {article['publication_year']}, Цитирований: {article['cited_by_count']}")
        if article['pdf_url']:
            print(f"   PDF: {article['pdf_url']}")
        elif article['doi_url']:
            print(f"   DOI: {article['doi_url']}")
    
    # Пример 3: Упрощенное получение ссылки
    print("\n=== Пример 3: Упрощенное получение ссылки ===")
    simple_search = "Deep learning"
    print(f"Быстрый поиск: '{simple_search}'")
    link = get_article_info(simple_search)
    if link:
        print(f"Ссылка: {link}")
    else:
        print("Ссылка не найдена")
    
    # Пример 4: Поиск по ключевым словам
    print("\n=== Пример 4: Поиск по ключевым словам ===")
    keywords = ["palladium", "catalysis", "nanoparticles"]
    print(f"Поиск по ключевым словам: {keywords}")
    keyword_results = search_articles_by_keywords(keywords, max_results=2)
    
    for article in keyword_results:
        print(f"\n{article['rank']}. {article['title']}")
        print(f"   Год: {article['publication_year']}")
        if article['pdf_url']:
            print(f"   PDF: {article['pdf_url']}")
        elif article['doi_url']:
            print(f"   DOI: {article['doi_url']}")

if __name__ == "__main__":
    main()
