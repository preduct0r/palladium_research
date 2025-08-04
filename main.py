"""
Модуль для поиска научных статей через OpenAlex API

Этот модуль предоставляет функции для поиска научных статей по названию
и получения ссылок на PDF файлы или DOI. Использует библиотеку pyalex
для взаимодействия с OpenAlex API и sci_hub.py для резервного поиска PDF.

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

# Импортируем SciHubSearcher для резервного поиска PDF
try:
    from sci_hub import SciHubSearcher
    SCIHUB_AVAILABLE = True
    logging.info("SciHub integration доступен")
except ImportError:
    SCIHUB_AVAILABLE = False
    logging.warning("SciHub integration недоступен - установите библиотеку scihub")

def try_scihub_search(doi_url: str) -> Optional[str]:
    """
    Попытка найти PDF через Sci-Hub используя DOI
    
    Args:
        doi_url (str): DOI ссылка статьи
        
    Returns:
        Optional[str]: PDF ссылка или None если не найдено
    """
    if not SCIHUB_AVAILABLE:
        return None
        
    try:
        # Извлекаем чистый DOI из URL
        if doi_url.startswith('https://doi.org/'):
            doi = doi_url.replace('https://doi.org/', '')
        elif doi_url.startswith('http://dx.doi.org/'):
            doi = doi_url.replace('http://dx.doi.org/', '')
        else:
            doi = doi_url
            
        # Инициализируем SciHub searcher
        scihub_searcher = SciHubSearcher()
        
        # Ищем статью по DOI
        result = scihub_searcher.search_paper_by_doi(doi)
        
        if result and result.get('status') == 'success':
            pdf_url = result.get('pdf_url')
            if pdf_url:
                logging.info(f"Найден PDF через Sci-Hub: {pdf_url}")
                return pdf_url
                
    except Exception as e:
        logging.warning(f"Ошибка при поиске через Sci-Hub: {str(e)}")
        
    return None

def is_pdf_url(url: str) -> bool:
    """
    Проверяет, ведет ли URL на PDF файл
    
    Args:
        url (str): URL для проверки
        
    Returns:
        bool: True если URL ведет на PDF, False иначе
    """
    if not url:
        return False
        
    url_lower = url.lower()
    
    # Очевидные PDF ссылки
    if url_lower.endswith('.pdf'):
        return True
        
    # PDF параметры в URL
    if 'pdf' in url_lower and ('render' in url_lower or 'download' in url_lower or 'view' in url_lower):
        return True
        
    # Известные PDF хостинги
    pdf_hosts = [
        'europepmc.org/articles/',
        'arxiv.org/pdf/',
        'biorxiv.org/content/',
        'researchgate.net/profile/',
        'pubs.rsc.org/en/content/articlepdf',
        'acs.org/doi/pdf',
        'nature.com/articles/',
        'science.org/doi/pdf',
        'cell.com/action/showPdf'
    ]
    
    for host in pdf_hosts:
        if host in url_lower:
            return True
    
    # НЕ PDF ссылки (DOI и подобные)
    non_pdf_patterns = [
        'doi.org/',
        'dx.doi.org/',
        'handle.net/',
        'openalex.org/',
        'semanticscholar.org/',
        'pubmed.ncbi.nlm.nih.gov/',
        'crossref.org/'
    ]
    
    for pattern in non_pdf_patterns:
        if pattern in url_lower:
            return False
            
    return False

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
            - journal: Название журнала/venue
            - journal_issn: ISSN журнала
            - journal_publisher: Издатель журнала
            
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
            'doi_url': None,
            'journal': None,
            'journal_issn': None,
            'journal_publisher': None
        }
        
        # Извлекаем информацию о журнале/venue
        primary_location = article.get('primary_location')
        if primary_location and primary_location.get('source'):
            source = primary_location['source']
            article_info['journal'] = source.get('display_name')
            
            # Извлекаем ISSN
            issn_l = source.get('issn_l')
            issn = source.get('issn')
            if issn_l:
                article_info['journal_issn'] = issn_l
            elif issn and len(issn) > 0:
                article_info['journal_issn'] = issn[0]
            
            # Извлекаем издателя
            article_info['journal_publisher'] = source.get('publisher')
            
            logging.info(f"Найден журнал: {article_info['journal']}")
        else:
            # Проверяем альтернативные источники
            locations = article.get('locations', [])
            for location in locations:
                if location.get('source') and location['source'].get('display_name'):
                    source = location['source']
                    article_info['journal'] = source.get('display_name')
                    article_info['journal_issn'] = source.get('issn_l') or (source.get('issn', [None])[0] if source.get('issn') else None)
                    article_info['journal_publisher'] = source.get('publisher')
                    logging.info(f"Найден журнал в альтернативных источниках: {article_info['journal']}")
                    break
        
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
            oa_url = open_access_info['oa_url']
            if is_pdf_url(oa_url):
                article_info['pdf_url'] = oa_url
                logging.info(f"Найдена PDF ссылка: {article_info['pdf_url']}")
            else:
                logging.info(f"oa_url не является PDF ссылкой: {oa_url}")
        
        # Если PDF не найден в oa_url, проверяем другие источники
        if not article_info['pdf_url']:
            locations = article.get('locations', [])
            for location in locations:
                pdf_url = location.get('pdf_url')
                if pdf_url and is_pdf_url(pdf_url):
                    article_info['pdf_url'] = pdf_url
                    logging.info(f"Найдена PDF ссылка в источниках: {article_info['pdf_url']}")
                    break
                elif pdf_url:
                    logging.info(f"URL в locations не является PDF ссылкой: {pdf_url}")
        
        # Если PDF не найден через OpenAlex, пробуем Sci-Hub
        if not article_info['pdf_url'] and article_info['doi_url']:
            logging.info("PDF не найден в OpenAlex, пробуем Sci-Hub...")
            scihub_pdf = try_scihub_search(article_info['doi_url'])
            if scihub_pdf:
                article_info['pdf_url'] = scihub_pdf
                article_info['pdf_source'] = 'scihub'  # Помечаем источник
            else:
                logging.info("PDF не найден и в Sci-Hub")
        
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
                'doi_url': None,
                'journal': None,
                'journal_issn': None,
                'journal_publisher': None
            }
            
            # Извлекаем информацию о журнале
            primary_location = article.get('primary_location')
            if primary_location and primary_location.get('source'):
                source = primary_location['source']
                article_info['journal'] = source.get('display_name')
                article_info['journal_issn'] = source.get('issn_l') or (source.get('issn', [None])[0] if source.get('issn') else None)
                article_info['journal_publisher'] = source.get('publisher')
            else:
                # Проверяем альтернативные источники
                locations = article.get('locations', [])
                for location in locations:
                    if location.get('source') and location['source'].get('display_name'):
                        source = location['source']
                        article_info['journal'] = source.get('display_name')
                        article_info['journal_issn'] = source.get('issn_l') or (source.get('issn', [None])[0] if source.get('issn') else None)
                        article_info['journal_publisher'] = source.get('publisher')
                        break
            
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
                oa_url = open_access_info['oa_url']
                if is_pdf_url(oa_url):
                    article_info['pdf_url'] = oa_url
                else:
                    logging.info(f"oa_url не является PDF ссылкой: {oa_url}")
            else:
                # Проверяем другие источники для PDF
                locations = article.get('locations', [])
                for location in locations:
                    pdf_url = location.get('pdf_url')
                    if pdf_url and is_pdf_url(pdf_url):
                        article_info['pdf_url'] = pdf_url
                        break
                    elif pdf_url:
                        logging.info(f"URL в locations не является PDF ссылкой: {pdf_url}")
            
            # Если PDF не найден через OpenAlex, пробуем Sci-Hub
            if not article_info['pdf_url'] and article_info['doi_url']:
                scihub_pdf = try_scihub_search(article_info['doi_url'])
                if scihub_pdf:
                    article_info['pdf_url'] = scihub_pdf
                    article_info['pdf_source'] = 'scihub'
            
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
            'doi_url': None,
            'journal': None,
            'journal_issn': None,
            'journal_publisher': None
        }
        
        # Извлекаем информацию о журнале
        primary_location = article.get('primary_location')
        if primary_location and primary_location.get('source'):
            source = primary_location['source']
            article_info['journal'] = source.get('display_name')
            article_info['journal_issn'] = source.get('issn_l') or (source.get('issn', [None])[0] if source.get('issn') else None)
            article_info['journal_publisher'] = source.get('publisher')
        else:
            # Проверяем альтернативные источники
            locations = article.get('locations', [])
            for location in locations:
                if location.get('source') and location['source'].get('display_name'):
                    source = location['source']
                    article_info['journal'] = source.get('display_name')
                    article_info['journal_issn'] = source.get('issn_l') or (source.get('issn', [None])[0] if source.get('issn') else None)
                    article_info['journal_publisher'] = source.get('publisher')
                    break
        
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
            oa_url = open_access_info['oa_url']
            if is_pdf_url(oa_url):
                article_info['pdf_url'] = oa_url
                logging.info(f"Найдена PDF ссылка: {article_info['pdf_url']}")
            else:
                logging.info(f"oa_url не является PDF ссылкой: {oa_url}")
        
        # Если PDF не найден в oa_url, проверяем другие источники
        if not article_info['pdf_url']:
            locations = article.get('locations', [])
            for location in locations:
                pdf_url = location.get('pdf_url')
                if pdf_url and is_pdf_url(pdf_url):
                    article_info['pdf_url'] = pdf_url
                    logging.info(f"Найдена PDF ссылка в источниках: {article_info['pdf_url']}")
                    break
                elif pdf_url:
                    logging.info(f"URL в locations не является PDF ссылкой: {pdf_url}")
        
        # Если PDF не найден через OpenAlex, пробуем Sci-Hub
        if not article_info['pdf_url'] and article_info['doi_url']:
            logging.info("PDF не найден в OpenAlex, пробуем Sci-Hub...")
            scihub_pdf = try_scihub_search(article_info['doi_url'])
            if scihub_pdf:
                article_info['pdf_url'] = scihub_pdf
                article_info['pdf_source'] = 'scihub'  # Помечаем источник
            else:
                logging.info("PDF не найден и в Sci-Hub")
        
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
    # article_title = "Direct conversion of phenols into primary anilines with hydrazine catalyzed by palladium"
    article_title = "The Effect of Addition of ppm-Order Pd to Fe-K Catalyst on Dehydrogenation of Ethylbenzene"
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
        
        # Показываем информацию о журнале
        if result['journal']:
            print(f"Журнал: {result['journal']}")
            if result['journal_issn']:
                print(f"ISSN: {result['journal_issn']}")
            if result['journal_publisher']:
                print(f"Издатель: {result['journal_publisher']}")
        
        if result['pdf_url']:
            pdf_source = result.get('pdf_source', 'openalex')
            source_label = ' (Sci-Hub)' if pdf_source == 'scihub' else ' (OpenAlex)'
            print(f"PDF ссылка{source_label}: {result['pdf_url']}")
        
        if result['doi_url']:
            print(f"DOI ссылка: {result['doi_url']}")
        
        if not result['pdf_url'] and not result['doi_url']:
            print("Ссылки на статью не найдены")
    else:
        print("Статья не найдена")
    



if __name__ == "__main__":
    main()
