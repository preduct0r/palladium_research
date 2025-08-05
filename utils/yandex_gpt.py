import requests
import json
from dotenv import load_dotenv
import os
import time
from urllib3.exceptions import NameResolutionError
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
                
        except (ConnectionError, NameResolutionError, Timeout) as e:
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