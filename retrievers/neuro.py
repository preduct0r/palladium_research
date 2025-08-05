import requests
from dotenv import load_dotenv, find_dotenv
import os

# Load environment variables from .env file
load_dotenv(find_dotenv())

# Идентификатор каталога (folderId) и IAM-токен для доступа к Yandex Search API
FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")
API_TOKEN = os.getenv("YANDEX_API_TOKEN")
SEARCH_API_GENERATIVE = os.getenv("YANDEX_SEARCH_API_GENERATIVE")


if __name__ == "__main__":
    # user_query = "Описание технологической схемы аффинажа палладия. Последние достижения науки и техники. Новые статьи и патенты"      
    user_query = "аффинаж палладия" 

    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messages": [
            {"content": user_query, "role": "ROLE_USER"}
        ],
        "folderId": FOLDER_ID,
        "site": {
            "site": [
                # "https://scholar.google.com/schhp?hl=ru&as_sdt=0,5",
                "https://elibrary.ru/",
                # "https://patents.google.com/"
            ]
        }
    }

    response = requests.post(SEARCH_API_GENERATIVE, headers=headers, json=payload)

    print(f"Status Code: {response.status_code}")
    print(f"Response Body: {response.text}")
    json_data = response.json()

    

    pass
       