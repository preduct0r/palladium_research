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
            - publication_date: Полная дата публикации (YYYY-MM-DD)
            - publication_month: Месяц публикации
            - publication_day: День публикации
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
        
        # Извлекаем дату публикации
        publication_date = article.get('publication_date')
        publication_month = None
        publication_day = None
        
        if publication_date:
            try:
                # Разбираем дату в формате YYYY-MM-DD
                date_parts = publication_date.split('-')
                if len(date_parts) >= 2:
                    publication_month = int(date_parts[1])
                if len(date_parts) >= 3:
                    publication_day = int(date_parts[2])
            except (ValueError, IndexError):
                # Если не удалось разобрать дату, оставляем None
                pass
        
        # Извлекаем информацию о статье
        article_info = {
            'title': article.get('title', 'Название не указано'),
            'authors': [author.get('author', {}).get('display_name', 'Неизвестный автор') 
                       for author in article.get('authorships', [])],
            'publication_year': article.get('publication_year'),
            'publication_date': publication_date,
            'publication_month': publication_month,
            'publication_day': publication_day,
            'is_open_access': article.get('open_access', {}).get('is_oa', False),
            'pdf_url': None,
            'doi_url': None
        }
        
        # Всегда заполняем DOI URL если доступен
        doi = article.get('doi')
        if doi:
            article_info['doi_url'] = doi
            logging.info(f"Найден DOI: {article_info['doi_url']}")
        else:
            # Альтернативный способ получения URL
            openalex_url = article.get('id')
            if openalex_url:
                article_info['doi_url'] = openalex_url
                logging.info(f"DOI не найден, используем OpenAlex URL: {article_info['doi_url']}")
        
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
            # Извлекаем дату публикации
            publication_date = article.get('publication_date')
            publication_month = None
            publication_day = None
            
            if publication_date:
                try:
                    # Разбираем дату в формате YYYY-MM-DD
                    date_parts = publication_date.split('-')
                    if len(date_parts) >= 2:
                        publication_month = int(date_parts[1])
                    if len(date_parts) >= 3:
                        publication_day = int(date_parts[2])
                except (ValueError, IndexError):
                    # Если не удалось разобрать дату, оставляем None
                    pass
            
            article_info = {
                'rank': i + 1,
                'title': article.get('title', 'Название не указано'),
                'authors': [author.get('author', {}).get('display_name', 'Неизвестный автор') 
                           for author in article.get('authorships', [])],
                'publication_year': article.get('publication_year'),
                'publication_date': publication_date,
                'publication_month': publication_month,
                'publication_day': publication_day,
                'is_open_access': article.get('open_access', {}).get('is_oa', False),
                'cited_by_count': article.get('cited_by_count', 0),
                'pdf_url': None,
                'doi_url': None
            }
            
            # Всегда заполняем DOI URL если доступен
            doi = article.get('doi')
            if doi:
                article_info['doi_url'] = doi
            else:
                openalex_url = article.get('id')
                if openalex_url:
                    article_info['doi_url'] = openalex_url
            
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
        # Используем правильное поле title.search для поиска по названию
        results = Works().filter(**{"title.search": title}).get()
        
        if not results:
            # Пытаемся альтернативный поиск с кавычками
            results = Works().search(f'"{title}"').get()
        
        if not results:
            # Последняя попытка - обычный поиск
            results = Works().search(title).get()
        
        if not results:
            logging.warning(f"Статья с точным названием '{title}' не найдена")
            return None
        
        # Берем первый результат и обрабатываем его
        article = results[0]
        
        # Извлекаем дату публикации
        publication_date = article.get('publication_date')
        publication_month = None
        publication_day = None
        
        if publication_date:
            try:
                # Разбираем дату в формате YYYY-MM-DD
                date_parts = publication_date.split('-')
                if len(date_parts) >= 2:
                    publication_month = int(date_parts[1])
                if len(date_parts) >= 3:
                    publication_day = int(date_parts[2])
            except (ValueError, IndexError):
                # Если не удалось разобрать дату, оставляем None
                pass
        
        # Извлекаем информацию о статье (копируем логику из search_article_link)
        article_info = {
            'title': article.get('title', 'Название не указано'),
            'authors': [author.get('author', {}).get('display_name', 'Неизвестный автор') 
                       for author in article.get('authorships', [])],
            'publication_year': article.get('publication_year'),
            'publication_date': publication_date,
            'publication_month': publication_month,
            'publication_day': publication_day,
            'is_open_access': article.get('open_access', {}).get('is_oa', False),
            'pdf_url': None,
            'doi_url': None
        }
        
        # Всегда заполняем DOI URL если доступен
        doi = article.get('doi')
        if doi:
            article_info['doi_url'] = doi
            logging.info(f"Найден DOI: {article_info['doi_url']}")
        else:
            # Альтернативный способ получения URL
            openalex_url = article.get('id')
            if openalex_url:
                article_info['doi_url'] = openalex_url
                logging.info(f"DOI не найден, используем OpenAlex URL: {article_info['doi_url']}")
        
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
        
        return article_info
        
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
    # article_title = "The Effect of Addition of ppm-Order Pd to Fe-K Catalyst on Dehydrogenation of Ethylbenzene"

    article_title = "Direct conversion of phenols into primary anilines with hydrazine catalyzed by palladium"
    print(f"Поиск статьи: '{article_title}'")
    result = search_by_exact_title(article_title)
    
    if result:
        print(f"Название: {result['title']}")
        print(f"Авторы: {', '.join(result['authors'][:3])}{'...' if len(result['authors']) > 3 else ''}")
        print(f"Год публикации: {result['publication_year']}")
        
        # Показываем детальную информацию о дате
        if result['publication_date']:
            print(f"Полная дата: {result['publication_date']}")
        if result['publication_month']:
            print(f"Месяц: {result['publication_month']}")
        if result['publication_day']:
            print(f"День: {result['publication_day']}")
        
        print(f"Открытый доступ: {'Да' if result['is_open_access'] else 'Нет'}")
        
        if result['pdf_url']:
            print(f"PDF ссылка: {result['pdf_url']}")
        
        if result['doi_url']:
            print(f"DOI ссылка: {result['doi_url']}")
        
        if not result['pdf_url'] and not result['doi_url']:
            print("Ссылки на статью не найдены")
    else:
        print("Статья не найдена")


if __name__ == "__main__":
    main()
