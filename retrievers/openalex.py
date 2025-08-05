#!/usr/bin/env python3
import requests
import json
import re
from pathlib import Path
from typing import List, Dict, Set

def search_openalex(query: str, per_page: int = 200, max_results: int = 1000) -> List[Dict]:
    """
    Поиск работ в OpenAlex по словосочетанию с дедубликацией.
    
    Args:
        query: поисковый запрос
        per_page: количество результатов на страницу (макс 200)
        max_results: максимальное количество результатов
    
    Returns:
        список уникальных работ
    """
    base_url = "https://api.openalex.org/works"
    all_results = []
    seen_ids: Set[str] = set()
    cursor = "*"
    
    while len(all_results) < max_results:
        params = {
            "search": query,  # Убираем кавычки - OpenAlex сам найдет словосочетания
            "per-page": min(per_page, max_results - len(all_results)),
            "cursor": cursor,
            "mailto": "researcher@example.com"
        }
        
        try:
            response = requests.get(base_url, params=params, timeout=30)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Ошибка запроса: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Статус код: {e.response.status_code}")
                print(f"Текст ответа: {e.response.text[:500]}")
            break
        
        data = response.json()
        results = data.get("results", [])
        
        if not results:
            break
            
        # Дедубликация по ID
        for work in results:
            work_id = work.get("id")
            if work_id and work_id not in seen_ids:
                seen_ids.add(work_id)
                all_results.append(work)
        
        # Проверяем, есть ли следующая страница
        meta = data.get("meta", {})
        next_cursor = meta.get("next_cursor")
        if not next_cursor:
            break
        cursor = next_cursor
        
        print(f"Загружено {len(all_results)} результатов...")
    
    return all_results

def search_with_pyalex(query: str, max_results: int = 25) -> List[Dict]:
    """
    Альтернативный поиск с использованием библиотеки pyalex (если установлена).
    """
    try:
        from pyalex import Works
        print("Используется библиотека pyalex...")
        
        # Получаем результаты через pyalex
        works = Works().search(query).get()
        
        # Ограничиваем количество результатов
        if len(works) > max_results:
            works = works[:max_results]
            
        return works
    except ImportError:
        print("Библиотека pyalex не установлена, используется базовый API...")
        return search_openalex(query, max_results=max_results)
    
def extract_openalex_pdfs(query, max_results=10):
    """Извлечение и скачивание PDF файлов из результатов поиска OpenAlex"""
    # Получаем результаты поиска
    results = search_with_pyalex(query, max_results)
    
    if not results:
        print("Результаты поиска не найдены")
        return []
    
    # Создаем папку для сохранения PDF в корневой директории проекта
    project_root = Path(__file__).parent.parent  # Поднимаемся на уровень выше из retrievers/
    output_dir = project_root / "data" / "1" / "openalex"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    downloaded_files = []
    
    print(f"Найдено {len(results)} результатов OpenAlex")
    print(f"Начинаем поиск и скачивание PDF в папку: {output_dir}")
    
    for i, work in enumerate(results[:max_results], 1):
        title = work.get('title', f'document_{i}')
        pdf_urls = []
        
        # Ищем PDF ссылки в разных местах
        # 1. best_oa_location
        best_oa = work.get('best_oa_location', {})
        if best_oa and best_oa.get('pdf_url'):
            pdf_urls.append(best_oa['pdf_url'])
        
        # 2. primary_location
        primary_loc = work.get('primary_location', {})
        if primary_loc and primary_loc.get('pdf_url'):
            pdf_urls.append(primary_loc['pdf_url'])
        
        # 3. locations array
        locations = work.get('locations', [])
        for location in locations:
            if location.get('pdf_url'):
                pdf_urls.append(location['pdf_url'])
        
        # 4. open_access.oa_url (может быть PDF)
        open_access = work.get('open_access', {})
        oa_url = open_access.get('oa_url', '')
        if oa_url and oa_url.lower().endswith('.pdf'):
            pdf_urls.append(oa_url)
        
        # Убираем дубликаты
        pdf_urls = list(set(pdf_urls))
        
        if not pdf_urls:
            print(f"{i}. Пропускаем: нет PDF ссылок для '{title}'")
            continue
        
        # Пробуем скачать первую доступную PDF ссылку
        downloaded = False
        for pdf_url in pdf_urls:
            try:
                # Очищаем название файла от недопустимых символов
                safe_filename = re.sub(r'[^\w\s-]', '', title).strip()
                safe_filename = re.sub(r'[-\s]+', '_', safe_filename)[:100]  # Ограничиваем длину
                
                # Генерируем имя файла
                filename = f"{i:02d}_{safe_filename}.pdf"
                filepath = output_dir / filename
                
                print(f"{i}. Скачиваем: {title}")
                print(f"   URL: {pdf_url}")
                
                # Скачиваем PDF файл
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                
                response = requests.get(pdf_url, headers=headers, timeout=30, stream=True)
                response.raise_for_status()
                
                # Проверяем, что это действительно PDF
                content_type = response.headers.get('content-type', '').lower()
                if 'pdf' not in content_type and not pdf_url.lower().endswith('.pdf'):
                    print(f"   Предупреждение: файл может не быть PDF (content-type: {content_type})")
                
                # Сохраняем файл
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                file_size = filepath.stat().st_size
                print(f"   Сохранено: {filename} ({file_size} байт)")
                
                downloaded_files.append({
                    'title': title,
                    'filename': filename,
                    'filepath': str(filepath),
                    'url': pdf_url,
                    'size': file_size,
                    'doi': work.get('doi', ''),
                    'year': work.get('publication_year', '')
                })
                
                downloaded = True
                break  # Успешно скачали, переходим к следующему
                
            except requests.exceptions.RequestException as e:
                print(f"   Ошибка при скачивании {pdf_url}: {e}")
                continue  # Пробуем следующую ссылку
            except Exception as e:
                print(f"   Неожиданная ошибка: {e}")
                continue
        
        if not downloaded:
            print(f"   Не удалось скачать ни одну из {len(pdf_urls)} PDF ссылок")
    
    print(f"\nСкачивание завершено. Успешно загружено: {len(downloaded_files)} файлов")
    return downloaded_files

def main():
    """Пример использования"""
    query = "аффинажа палладия"
    
    if not query:
        print("Пустой запрос, используем пример: 'artificial intelligence'")
        query = "artificial intelligence"
    
    print(f"Поиск по запросу: {query}")
    
    print("1. Поиск результатов")
    print("2. Поиск и скачивание PDF")
    choice = input("Выберите действие (1 или 2): ").strip()
    
    if choice == "2":
        # Тестируем функцию скачивания PDF
        downloaded_files = extract_openalex_pdfs(query, max_results=5)
        
        if downloaded_files:
            print("\nИнформация о скачанных файлах:")
            for file_info in downloaded_files:
                print(f"- {file_info['filename']} ({file_info['size']} байт)")
                print(f"  DOI: {file_info['doi']}, Год: {file_info['year']}")
    else:
        # Обычный поиск без скачивания
        results = search_with_pyalex(query)
        
        print(f"\nНайдено {len(results)} уникальных работ:")
        for i, work in enumerate(results[:5], 1):  # показываем первые 5
            title = work.get('title', 'Без названия')
            doi = work.get('doi', 'Нет')
            year = work.get('publication_year', 'Неизвестно')
            cited_count = work.get('cited_by_count', 0)
            
            print(f"{i}. {title}")
            print(f"   DOI: {doi}")
            print(f"   Год: {year}")
            print(f"   Цитирований: {cited_count}")
            
            # Показываем авторов если есть
            authors = work.get('authorships', [])
            if authors:
                author_names = [auth.get('author', {}).get('display_name', 'Неизвестно') 
                              for auth in authors[:3]]  # первые 3 автора
                print(f"   Авторы: {', '.join(author_names)}")
                if len(authors) > 3:
                    print(f"   ... и ещё {len(authors) - 3} авторов")
            print()

if __name__ == "__main__":
    main()
