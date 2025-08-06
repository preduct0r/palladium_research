import os
from dotenv import load_dotenv, find_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser

import uuid
from langchain.vectorstores import Chroma
from langchain.storage import InMemoryStore
from langchain.schema.document import Document
from langchain.embeddings import OpenAIEmbeddings
from langchain.retrievers.multi_vector import MultiVectorRetriever
from langchain_core.runnables import RunnablePassthrough, RunnableLambda

from unstructured.partition.pdf import partition_pdf
from pathlib import Path

from utils.rag import parse_docs, build_prompt
from utils.initial_article_processing import get_article_chunks, summarize_article_data, get_article_vectorstore, get_article_title_info
from utils.difficult_question_processing import download_relevant_pdfs, get_relevant_data_chunks, get_relevant_data_vectorstore
from dotenv import load_dotenv, find_dotenv
# ================================
# Load environment variables from the nearest .env file
dotenv_path = find_dotenv()
if not dotenv_path:
    raise FileNotFoundError("'.env' file not found. Please create one in the project root.")
load_dotenv(dotenv_path)

OPENAI_API_KEY = os.getenv("YANDEX_API_KEY")
folder_id = os.getenv("YANDEX_FOLDER_ID")
model = ChatOpenAI(base_url="https://llm.api.cloud.yandex.net/v1",  temperature=0.5, model_name=f"gpt://{folder_id}/qwen3-235b-a22b-fp8/latest")

article_path="/home/ubuntu/kotov_projects/palladium_research/articles/The Effect of Addition of ppm-Order-Pd to Fe-K Catalyst on Dehydrogenation of Ethylbenzene.pdf"
article_name = Path(article_path).stem.replace(" ", "_")

# ================================
# Извлечение информации о статье из OpenAlex
print("Извлекаем информацию о статье из OpenAlex...")
get_article_title_info(article_name)

texts, tables = get_article_chunks(article_path)

text_summaries, table_summaries = summarize_article_data(texts, tables)
article_retriever = get_article_vectorstore(texts, text_summaries, tables, table_summaries)

chain_with_sources = {
    "context": article_retriever | RunnableLambda(parse_docs),
    "question": RunnablePassthrough(),
} | RunnablePassthrough().assign(
    response=(
        RunnableLambda(build_prompt)
        | model
        | StrOutputParser()
    )
)

# Создаем папку для сохранения ответов
answers_dir = Path("data") / article_name / "answers"
answers_dir.mkdir(parents=True, exist_ok=True)

questions_and_files = [   
    ("Напиши одним предложением длинной не боллее 15 слов о какой промышленной технологии идет речь в этой статье. Выведи только название технологии", "technology.txt"),
    ("Какова основная идея статьи?", "idea.txt"),
    ("Какое направление (тематика) у этой статьи?", "tematic.txt"),
    ("Потенциальное потребление палладия согласно статье, кг", "potential_consumption.txt"),
]

for question, filename in questions_and_files:
    response = chain_with_sources.invoke(question)

    print("Response:", response['response'])
    
    # Сохраняем ответ в файл
    file_path = answers_dir / filename
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(response['response'])
    print(f"Ответ сохранен в: {file_path}")

    print("\n\nContext:")
    for text in response['context']['texts']:
        print(text.text)
        print("Page number: ", text.metadata.page_number)
        print("\n" + "-"*50 + "\n")



# ================================
# Process difficult questions
# Questions that demands context
questions_demands_search = [
    "Уровень развития технологии <технология>",
    # "Новизна применения палладия в <технология>",
    # "Научно-техническая реализуемость внедрения палладия в <технология>",
    # "Коммерческий потенциал внедрения палладия в <технология>",
    # "Конкурентные преимущества палладия в <технология>",
    # "Уровень готовности <технология> с палладием",
    # "Перепективность рынка разработки по <технология>",
    # "Уровень рыночного коммерческого потенциала по <технология>",
    # "Какова сложность разработки по <технология>?",
    # "Какова сложность внедрения <технология>?",
    # "Каков потенциал коммерциализации <технология>?",
    # "Какова предполагаемая длительность разработки <технология>?",
]

yandex_chunks, all_keywords = download_relevant_pdfs(questions_demands_search, article_name)

# Путь к папке с данными статьи
data_dir = Path("data") / article_name
relevant_data_chunks = get_relevant_data_chunks(data_dir)
relevant_data_retriever = get_relevant_data_vectorstore(relevant_data_chunks+yandex_chunks)


relevant_chain_with_sources = {
    "context": relevant_data_retriever | RunnableLambda(parse_docs),
    "question": RunnablePassthrough(),
} | RunnablePassthrough().assign(
    response=(
        RunnableLambda(build_prompt)
        | ChatOpenAI(model="gpt-4o-mini")
        | StrOutputParser()
    )
)
response = relevant_chain_with_sources.invoke("Уровень развития аффинажа палладия")
response