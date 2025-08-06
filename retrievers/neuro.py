import requests
from dotenv import load_dotenv, find_dotenv
import os

# Load environment variables from .env file
load_dotenv(find_dotenv())

# Идентификатор каталога (folderId) и IAM-токен для доступа к Yandex Search API
FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")
API_TOKEN = os.getenv("YANDEX_API_TOKEN")
SEARCH_API_GENERATIVE = os.getenv("YANDEX_SEARCH_API_GENERATIVE")


def get_neuro_response(user_query):
    """
    Отправляет запрос к Yandex Search API и возвращает ответ
    
    Args:
        user_query (str): Запрос пользователя
        
    Returns:
        dict: JSON ответ от API
    """
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messages": [
            {"content": user_query, "role": "ROLE_USER"}
        ],
        "folderId": FOLDER_ID,
        # "site": {
        #     "site": [
        #         # "https://scholar.google.com/schhp?hl=ru&as_sdt=0,5",
        #         "https://elibrary.ru/",
        #         # "https://patents.google.com/"
        #     ]
        # }
    }

    response = requests.post(SEARCH_API_GENERATIVE, headers=headers, json=payload)
    
    if response.status_code == 200:
        return response.json()
    else:
        return {
            "error": f"API request failed with status code: {response.status_code}",
            "response_text": response.text
        }


if __name__ == "__main__":
    # user_query = "Описание технологической схемы аффинажа палладия. Последние достижения науки и техники. Новые статьи и патенты"      
    user_query = "аффинаж палладия" 
    
    result = get_neuro_response(user_query)
    
    print(f"Response: {result}")
       