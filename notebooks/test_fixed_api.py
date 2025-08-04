import requests
import json
from dotenv import load_dotenv
import os

# Загружаем переменные окружения
load_dotenv()

# Получаем API ключи (используем рабочий)
api_key = os.getenv("YC_API_KEY")  # Этот ключ работает согласно диагностике
folder_id = os.getenv("YANDEX_FOLDER_ID")

print(f"API Key: {'***' + api_key[-4:] if api_key else 'Not found'}")
print(f"Folder ID: {folder_id}")

def yandex_gpt_request(prompt, model="yandexgpt", temperature=0.6, max_tokens=2000):
    """
    Функция для отправки запросов к YandexGPT через нативный API
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
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            return result["result"]["alternatives"][0]["message"]["text"]
        else:
            print(f"Ошибка: HTTP {response.status_code}")
            print(response.text)
            return None
            
    except Exception as e:
        print(f"Ошибка запроса: {e}")
        return None

# Тестируем исправленный API
print("\n=== Тестирование исправленного API ===")
test_prompt = "Что умеют большие языковые модели?"

print(f"Вопрос: {test_prompt}")
print("\nОтвет YandexGPT:")
response = yandex_gpt_request(test_prompt, model="yandexgpt")
if response:
    print(response)
else:
    print("Не удалось получить ответ")

print("\n" + "="*50)
print("Тест завершен успешно!") 