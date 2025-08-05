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
from utils.difficult_question_processing import download_relevant_pdfs
from dotenv import load_dotenv, find_dotenv
# ================================
# Load environment variables from the nearest .env file
dotenv_path = find_dotenv()
if not dotenv_path:
    raise FileNotFoundError("'.env' file not found. Please create one in the project root.")
load_dotenv(dotenv_path)

article_path="/home/den/Documents/Nornikel/deep_research/palladium/27208.pdf"
article_name = Path(article_path).stem.replace(" ", "_")

# ================================
# Извлечение информации о статье из OpenAlex
print("Извлекаем информацию о статье из OpenAlex...")

# Сначала получаем чанки статьи для извлечения названия
texts, tables = get_article_chunks(article_path)

get_article_title_info(texts, article_name)

# ================================
# Продолжаем с основной обработкой статьи
texts, tables = get_article_chunks(article_path)

text_summaries, table_summaries = summarize_article_data(texts, tables)
article_retriever = get_article_vectorstore(texts, text_summaries, tables, table_summaries)

chain_with_sources = {
    "context": article_retriever | RunnableLambda(parse_docs),
    "question": RunnablePassthrough(),
} | RunnablePassthrough().assign(
    response=(
        RunnableLambda(build_prompt)
        | ChatOpenAI(model="gpt-4o-mini")
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
    "Уровень развития технологии",
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

chunks, all_keywords = download_relevant_pdfs(questions_demands_search, article_name)



