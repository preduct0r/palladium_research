import os
import requests
import time
import json
import base64
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
from dotenv import load_dotenv

class YandexSearch:
    """
    Веб-поиск по интернету через Yandex Search API v1 (синхронный).
    """

    def __init__(self, query: str, headers: dict = None, query_domains: list = None):
        """
        Args:
            query (str): строка поискового запроса.
            headers (dict): опционально можно передать {
                "yandex_api_key": "<API-ключ>",
                "yandex_folder_id": "<Folder-ID>"
            }
            query_domains (list): опционально список доменов, по которым нужно ограничить поиск,
                                   например ["example.com", "another.org"].
        """
        
        # Загружаем переменные из .env файла
        load_dotenv()
        
        self.query = query if len(query)<400 else query[:400]
        self.headers = headers or {}
        self.query_domains = query_domains or []


        self.api_key = os.environ.get("YC_SEARCH_API")
        self.folder_id = os.environ.get("YC_FOLDER_ID")

        self.endpoint = "https://searchapi.api.cloud.yandex.net/v2/web/search"

    def extract_yandex_snippets(self, max_results=1):
        """
        Выполняет запрос к Yandex Search API. Если приходит rawData (XML в Base64),
        декодирует, парсит с помощью _parse_xml_results и возвращает список словарей.
        Иначе возвращает items из JSON.

        """
        search_query = self.query
        search_body = {
            "query": {"searchType": "SEARCH_TYPE_RU", "queryText": search_query,"page" :0,},
            "region": "225",
            "l10N": "ru",
            
            "folderId": self.folder_id,
        }


        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json"
        }

        for attempt in range(3):
            try:
                response = requests.post(
                    self.endpoint, headers=headers, json=search_body, timeout=15
                )
                response.raise_for_status()
                break
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                raise Exception(f"Сбой после 3 попыток: {e}")
            except requests.exceptions.HTTPError:
                text = response.text
                try:
                    text = json.dumps(response.json(), indent=2, ensure_ascii=False)
                except:
                    pass
                raise Exception(f"HTTP {response.status_code}: {text}")

   
        try:
            data = response.json()
        except json.JSONDecodeError:
            raise Exception(f"Невалидный JSON: {response.text[:200]}")

        raw_b64 = data.get("rawData") or data.get("response", {}).get("rawData")
        if raw_b64:
            try:
                xml = base64.b64decode(raw_b64).decode("utf-8")
            except Exception as e:
                raise Exception(f"Ошибка декодирования rawData: {e}")
            return self._parse_xml_results(xml, max_results)

     
        if "result" not in data:
            raise Exception(f"Неожиданная структура ответа: {json.dumps(data, indent=2, ensure_ascii=False)}")

        return data["result"].get("items", [])[:max_results]
        
    def _parse_xml_results(self, xml: str, max_results: int) -> list[dict]:
        import xml.etree.ElementTree as ET
        import html

        def strip_outer_quotes(s: str) -> str:
            return s[1:-1] if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"') else s

        def normalize_newlines(s: str) -> str:
            # аккуратно разворачиваем только \n, \r, \t — не трогаем кириллицу
            return s.replace("\\n", "\n").replace("\\r", "\r").replace("\\t", "\t")

        def extract_snippets(xml_text: str) -> list[str]:
            xml_text = normalize_newlines(strip_outer_quotes(xml_text))
            root = ET.fromstring(xml_text)

            snippets = []
            for p in root.findall(".//group/doc/passages/passage"):
                # берём чистый текст, склеивая текст узла и вложенных (в т.ч. <hlword>)
                txt = "".join(p.itertext()).strip()
                txt = html.unescape(txt)  # на всякий — декодируем &amp; и т.п.
                if txt:
                    snippets.append(txt)
            return snippets

        snippets = extract_snippets(xml)
        return snippets[:max_results]


if __name__ == "__main__":
    yandex_search = YandexSearch("Уровень развития аффинажа палладия")
    results = yandex_search.extract_yandex_snippets(max_results=15)
    print(results)  