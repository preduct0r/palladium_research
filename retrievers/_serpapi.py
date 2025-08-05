import os
import requests
import re
from urllib.parse import urlparse
from pathlib import Path
from serpapi import GoogleScholarSearch
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

def scholar_search(query, api_key=None):
    """Поиск в Google Scholar по словосочетаниям с фильтрацией PDF"""
    params = {
        "engine": "google_scholar",
        "q": query,
        "api_key": api_key or os.getenv("SERPAPI_KEY")
    }
    
    search = GoogleScholarSearch(params)
    results = search.get_dict()
    
    # Получаем органические результаты
    organic_results = results.get("organic_results", [])
    
    # Фильтруем только результаты с PDF ссылками
    pdf_results = []
    for result in organic_results:
        # Проверяем наличие PDF в основной ссылке
        link = result.get('link', '')
        if link.lower().endswith('.pdf'):
            result['pdf_link'] = link
            pdf_results.append(result)
        # Проверяем наличие PDF в дополнительных ссылках
        elif 'resources' in result:
            for resource in result['resources']:
                if resource.get('file_format', '').upper() == 'PDF':
                    result['pdf_link'] = resource.get('link', '')
                    pdf_results.append(result)
                    break
    
    return pdf_results

def print_results(results):
    """Вывод результатов поиска с PDF ссылками"""
    for i, result in enumerate(results[:5], 1):
        print(f"{i}. {result.get('title', 'Нет заголовка')}")
        print(f"   Авторы: {result.get('authors', 'Неизвестно')}")
        print(f"   Год: {result.get('year', 'Неизвестно')}")
        print(f"   PDF ссылка: {result.get('pdf_link', 'Нет PDF ссылки')}")
        print(f"   Основная ссылка: {result.get('link', 'Нет ссылки')}")
        print()

def extract_serpapi_pdfs(query, max_results=10, article_name="default"):
    """Извлечение и скачивание PDF файлов из результатов поиска Google Scholar"""
    # Получаем результаты поиска
    results = scholar_search(query)
    
    if not results:
        print("Результаты поиска не найдены")
        return []
    
    # Создаем папку для сохранения PDF с учетом названия статьи
    output_dir = Path("data") / article_name / "serpapi"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    downloaded_files = []
    
    print(f"Найдено {len(results)} результатов с PDF ссылками")
    print(f"Начинаем скачивание в папку: {output_dir}")
    
    for i, result in enumerate(results[:max_results], 1):
        pdf_link = result.get('pdf_link', '')
        title = result.get('title', f'document_{i}')
        
        if not pdf_link:
            print(f"{i}. Пропускаем: нет PDF ссылки для '{title}'")
            continue
        
        try:
            # Очищаем название файла от недопустимых символов
            safe_filename = re.sub(r'[^\w\s-]', '', title).strip()
            safe_filename = re.sub(r'[-\s]+', '_', safe_filename)[:100]  # Ограничиваем длину
            
            # Генерируем имя файла
            filename = f"{i:02d}_{safe_filename}.pdf"
            filepath = output_dir / filename
            
            print(f"{i}. Скачиваем: {title}")
            print(f"   URL: {pdf_link}")
            
            # Скачиваем PDF файл
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(pdf_link, headers=headers, timeout=30, stream=True)
            response.raise_for_status()
            
            # Проверяем, что это действительно PDF
            content_type = response.headers.get('content-type', '').lower()
            if 'pdf' not in content_type and not pdf_link.lower().endswith('.pdf'):
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
                'url': pdf_link,
                'size': file_size
            })
            
        except requests.exceptions.RequestException as e:
            print(f"   Ошибка при скачивании: {e}")
        except Exception as e:
            print(f"   Неожиданная ошибка: {e}")
    
    print(f"\nСкачивание завершено. Успешно загружено: {len(downloaded_files)} файлов")
    return downloaded_files


if __name__ == "__main__":
    # Пример использования
    query = "Описание технологической схемы аффинажа палладия. Последние достижения науки и техники. Новые статьи и патенты"
    
    print("1. Поиск результатов")
    print("2. Поиск и скачивание PDF")
    choice = input("Выберите действие (1 или 2): ").strip()
    
    if choice == "2":
        # Тестируем функцию скачивания PDF
        downloaded_files = extract_serpapi_pdfs(query, max_results=5)
        
        if downloaded_files:
            print("\nИнформация о скачанных файлах:")
            for file_info in downloaded_files:
                print(f"- {file_info['filename']} ({file_info['size']} байт)")
    else:
        # Обычный поиск без скачивания
        results = scholar_search(query)
        
        if results:
            print(f"\nНайдено результатов: {len(results)}")
            print("Топ-5 результатов:\n")
            print_results(results)
        else:
            print("Результаты не найдены")


