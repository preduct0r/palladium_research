from unstructured.partition.pdf import partition_pdf
from pathlib import Path

from utils.rag import parse_docs, build_prompt
from utils.initial_article_processing import get_article_chunks, summarize_article_data, get_article_vectorstore, get_article_title_info
from utils.difficult_question_processing import download_relevant_pdfs_and_chunks, get_relevant_data_chunks, get_relevant_data_vectorstore
from dotenv import load_dotenv, find_dotenv

from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser

from dotenv import load_dotenv, find_dotenv
# ================================
# Load environment variables from the nearest .env file
dotenv_path = find_dotenv()
if not dotenv_path:
    raise FileNotFoundError("'.env' file not found. Please create one in the project root.")
load_dotenv(dotenv_path)

article_path=os.getenv("ARTICLE_PATH")
article_name = Path(article_path).stem.replace(" ", "_")


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

yandex_chunks, all_keywords = download_relevant_pdfs_and_chunks(questions_demands_search, article_name)

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