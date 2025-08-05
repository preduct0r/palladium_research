import os
from langchain_community.embeddings.gigachat import GigaChatEmbeddings
from dotenv import load_dotenv      
from langchain_community.vectorstores import Chroma
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser

from langchain_core.prompts import ChatPromptTemplate
import re


from retrievers._serpapi import extract_serpapi_pdfs
from retrievers.yandex_search import YandexSearch
from retrievers.openalex import extract_openalex_pdfs

load_dotenv()

# Initialize environment variables from .env
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY")
# Convert tracing flag to boolean
LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() in ("true", "1", "yes")



# Questions that demands context
questions_demands_search = [
    "Уровень развития технологии под которую делается продукт",
    "Новизна применения палладия в данной технологии",
    "Научно-техническая реализуемость внедрения палладия в данной технологии",
    "Коммерческий потенциал внедрения палладия в данной технологии",
    "Конкурентные преимущества палладия в данной технологии",
    "Уровень готовности технологии с палладием",
    "Потенциальное потребление палладия, кг",
    "Перепективность рынка (разработка)",
    "Уровень рыночного потенциала(коммерция)",
    "Какова сложность разработки технологии?",
    "Какова сложность внедрения технологии?",
    "Каков потенциал коммерциализации технологии?",
    "Какова предполагаемая длительность разработки?",
]



_embeddings = GigaChatEmbeddings(model = "EmbeddingsGigaR",credentials= os.environ.get("GIGACHAT_CREDENTIALS"),scope =os.environ.get("GIGACHAT_API_CORP") , verify_ssl_certs = False)

chroma_vector_store = Chroma(collection_name="relevant_data", embedding_function=_embeddings)

with open("temp_files/idea.txt") as f:
    idea = f.read()
with open("temp_files/technology.txt") as f:
    technology = f.read()
with open("temp_files/tematic.txt") as f:
    tematic = f.read()
with open("prompts/get_keywords.txt") as f:
    serp_prompt_template = f.read()
with open("prompts/get_search_query.txt") as f:
    search_query_template = f.read()
model = ChatOpenAI(temperature=0.5, model_name="gpt-4o")

all_keywords = {}
chunks = {}

for question in questions_demands_search:
    # serp_prompt = serp_prompt_template.replace("<QUESTION>", question).replace("<IDEA>", idea).replace("<TECHNOLOGY>", technology).replace("<TEMATIC>", tematic)
    # serp_chain = ChatPromptTemplate.from_template(serp_prompt) | model | StrOutputParser()
    # # The prompt is already fully formed, so we pass an empty dictionary to invoke.
    # raw_keywords = serp_chain.invoke({})
    
    # # Очищаем результат от лишнего текста и получаем только ключевые слова
    # keywords = raw_keywords.strip()
    # # Удаляем возможные префиксы типа "Keywords:", "Answer:", etc.
    # keywords = re.sub(r'^[^:]*:\s*', '', keywords)
    # # Удаляем лишние пробелы и переносы строк
    # keywords = re.sub(r'\s+', ' ', keywords).strip()
    
    # print(f"Вопрос: {question}")
    # print(f"Ключевые слова: {keywords}")
    # all_keywords.add(keywords)

    # ================================
    query_prompt = search_query_template.replace("<QUESTION>", question).replace("<IDEA>", idea).replace("<TECHNOLOGY>", technology).replace("<TEMATIC>", tematic)
    query_chain = ChatPromptTemplate.from_template(query_prompt) | model | StrOutputParser()
    # The prompt is already fully formed, so we pass an empty dictionary to invoke.
    _query = query_chain.invoke({})
    yandex_snippets = YandexSearch(_query).extract_yandex_snippets()
    chunks.add(yandex_snippets)

    # ================================
    
     


# all_keywords = {"дегидрирование этилбензола", "палладий катализатор"}

# for keyword in all_keywords:
#     openalex_results = extract_openalex_pdfs(keyword)









