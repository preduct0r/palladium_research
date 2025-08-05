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


        self.api_key = self.headers.get("yandex_api_key") or self._get_api_key()
        self.folder_id = self.headers.get("yandex_folder_id") or self._get_folder_id()

        self.endpoint = "https://searchapi.api.cloud.yandex.net/v2/web/search"

    def _get_api_key(self) -> str:
        api_key = os.environ.get("YC_SEARCH_API") or os.environ.get("YC_API_KEY")
        if not api_key:
            raise Exception(
                "Yandex API key не найден. "
                "Установите переменную окружения YC_API_KEY или YC_SEARCH_API."
            )
        return api_key

    def _get_folder_id(self) -> str:
        folder_id = os.environ.get("YC_FOLDER_ID")
        if not folder_id:
            raise Exception(
                "Yandex Folder ID не найден. "
                "Установите переменную окружения YC_FOLDER_ID."
            )
        return folder_id

    def search(self, max_results=1):
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
        try:
            root = ET.fromstring(xml)
        except ET.ParseError as e:
            raise Exception(f"Ошибка разбора XML: {e}")

        results = []
        for group in root.findall(".//group"):
            doc = group.find("doc")
            if doc is None:
                continue

            title = doc.findtext("title", default="").strip()
            url   = doc.findtext("url",   default="").strip()

            snippet = ""
            passages = doc.find("passages")
            if passages is not None:
   
                texts = []
                for p in passages.findall("passage"):
                    full = "".join(p.itertext()).strip()
                    if full:
                        texts.append(full)
                snippet = " ".join(texts)

            if title and url:
                results.append({"title": title, "href": url, "snippet": snippet})


        if self.query_domains:
            results1 = self.filter_results_by_domain(results)
            if results1:
                results = results1
        return results
    def filter_results_by_domain(self,results):
        """
        Фильтрует результаты по списку доменов.

        Args:
            results (list): список словарей результатов, как возвращает search().
            allowed_domains (list): список доменов, например ["eda.ru", "russianfood.com"].

        Returns:
            list: отфильтрованные результаты
        """
        filtered = []
        for item in results:
            parsed_url = urlparse(item["href"])
            domain = parsed_url.netloc.replace("www.", "")
            if domain in self.query_domains:
                filtered.append(item)
        return filtered