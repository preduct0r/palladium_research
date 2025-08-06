import requests
import json
from dotenv import load_dotenv
import os
import re
import time
from urllib3.exceptions import NewConnectionError
from requests.exceptions import ConnectionError, Timeout, RequestException

# Загружаем переменные окружения
load_dotenv()

# Получаем API ключи (используем рабочий)
api_key = os.getenv("YC_API_KEY")  # Этот ключ работает согласно диагностике
folder_id = os.getenv("YANDEX_FOLDER_ID")

print(f"API Key: {'***' + api_key[-4:] if api_key else 'Not found'}")
print(f"Folder ID: {folder_id}")

def yandex_gpt_request(prompt, model="yandexgpt", temperature=0.6, max_tokens=2000, max_retries=3):
    """
    Функция для отправки запросов к YandexGPT через нативный API
    Добавлена логика повторных попыток для устойчивости к сетевым сбоям
    """
    
    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    
    headers = {
        "Authorization": f"Api-Key {api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "modelUri": f"gpt://b1gcsj6abocbljovl1do/yandexgpt-lite/latest",
        "completionOptions": {
            "stream": False,
            "temperature": temperature,
            "maxTokens": str(max_tokens)
        },
        "messages": [
            {
                "role": "user",
                "text": prompt
            }
        ]
    }
    
    for attempt in range(max_retries):
        try:
            print(f"Попытка {attempt + 1}/{max_retries}...")
            response = requests.post(url, headers=headers, json=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                return result["result"]["alternatives"][0]["message"]["text"]
            else:
                print(f"Ошибка: HTTP {response.status_code}")
                print(response.text)
                if response.status_code >= 500 and attempt < max_retries - 1:
                    print(f"Серверная ошибка, повторная попытка через 2 секунды...")
                    time.sleep(2)
                    continue
                return None
                
        except (ConnectionError, NewConnectionError, Timeout) as e:
            print(f"Сетевая ошибка на попытке {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2  # Экспоненциальная задержка
                print(f"Повторная попытка через {wait_time} секунд...")
                time.sleep(wait_time)
                continue
            else:
                print("Все попытки исчерпаны")
                return None
                
        except RequestException as e:
            print(f"Ошибка запроса на попытке {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                print(f"Повторная попытка через 2 секунды...")
                time.sleep(2)
                continue
            else:
                return None
                
        except Exception as e:
            print(f"Неожиданная ошибка на попытке {attempt + 1}: {e}")
            return None

    return None


def translate_keywords(keywords):
    """
    Переводит список ключевых слов с русского языка на английский с помощью YandexGPT
    
    Args:
        keywords (list): Список ключевых слов/словосочетаний на русском языке
        
    Returns:
        list: Список переведенных ключевых слов на английском языке
    """
    if not keywords:
        return []
    
    # Объединяем ключевые слова в строку для перевода
    keywords_text = ", ".join(keywords)
    
    # Создаем промпт для перевода
    prompt = f"""Переведи следующие ключевые слова и словосочетания с русского языка на английский язык. 
Сохрани тот же формат - через запятую и пробел. 
Переводи точно и кратко, используя наиболее подходящие английские термины.

Ключевые слова: {keywords_text}

Переведенные ключевые слова:"""
    
    try:
        # Получаем перевод от YandexGPT
        translated_response = yandex_gpt_request(prompt, temperature=0.3, max_tokens=1000)
        
        if translated_response:
            # Очищаем ответ от возможных префиксов
            translated_text = translated_response.strip()
            translated_text = re.sub(r'^[^:]*:\s*', '', translated_text)
            translated_text = re.sub(r'\s+', ' ', translated_text).strip()
            
            # Разбиваем на список
            translated_keywords = [kw.strip() for kw in translated_text.split(",") if kw.strip()]
            
            # Дополнительная очистка от знаков препинания в конце
            cleaned_keywords = []
            for kw in translated_keywords:
                # Убираем точки, запятые и другие знаки препинания в конце
                cleaned_kw = re.sub(r'[.,;:!?]+$', '', kw.strip())
                if cleaned_kw:
                    cleaned_keywords.append(cleaned_kw)
            
            print(f"Исходные ключевые слова: {keywords}")
            print(f"Переведенные ключевые слова: {cleaned_keywords}")
            
            return cleaned_keywords
        else:
            print("Ошибка при переводе ключевых слов, возвращаем исходный список")
            return keywords
            
    except Exception as e:
        print(f"Ошибка при переводе ключевых слов: {e}")
        return keywords


if __name__ == "__main__":
    # Тестируем исправленный API
    print("\n=== Тестирование API с повторными попытками ===")
    test_prompt = "Что умеют большие языковые модели?"

    print(f"Вопрос: {test_prompt}")
    print("\nОтвет YandexGPT:")
    response = yandex_gpt_request(test_prompt, model="yandexgpt")
    if response:
        print(response)
    else:
        print("Не удалось получить ответ после всех попыток")

    print("\n" + "="*50)
    print("Тест завершен!") 