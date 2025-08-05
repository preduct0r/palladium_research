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

from utils.rag import parse_docs, build_prompt
from utils.initial_article_processing import get_article_chunks, summarize_article_data, get_article_vectorstore
from utils.difficult_question_processing import download_relevant_pdfs
from dotenv import load_dotenv, find_dotenv
# ================================
# Load environment variables from the nearest .env file
dotenv_path = find_dotenv()
if not dotenv_path:
    raise FileNotFoundError("'.env' file not found. Please create one in the project root.")
load_dotenv(dotenv_path)

article_path="/home/den/Documents/Nornikel/deep_research/palladium/27208.pdf"
# texts, tables = get_article_chunks(article_path)

# text_summaries, table_summaries = summarize_article_data(texts, tables)
# article_retriever = get_article_vectorstore(texts, text_summaries, tables, table_summaries)

# chain_with_sources = {
#     "context": article_retriever | RunnableLambda(parse_docs),
#     "question": RunnablePassthrough(),
# } | RunnablePassthrough().assign(
#     response=(
#         RunnableLambda(build_prompt)
#         | ChatOpenAI(model="gpt-4o-mini")
#         | StrOutputParser()
#     )
# )

# for question in [   
#     "Напиши одним предложением длинной не боллее 15 слов о какой промышленной технологии идет речь в этой статье. Выведи только название технологии",
#     "Какова основная идея статьи?",
#     "Какое направление (тематика) у этой статьи?",
#     ]:
#     response = chain_with_sources.invoke(question)

#     print("Response:", response['response'])

#     print("\n\nContext:")
#     for text in response['context']['texts']:
#         print(text.text)
#         print("Page number: ", text.metadata.page_number)
#         print("\n" + "-"*50 + "\n")



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

chunks, all_keywords = download_relevant_pdfs(questions_demands_search)



