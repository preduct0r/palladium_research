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
from retrievers.openalex import find_article_by_title
from pathlib import Path


from utils.rag import parse_docs, build_prompt




# GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY")
# Convert tracing flag to boolean
LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() in ("true", "1", "yes")
# Initialize environment variables from .env
OPENAI_API_KEY = os.getenv("YANDEX_API_KEY")
folder_id = os.getenv("YANDEX_FOLDER_ID")

embedding_model = "intfloat/multilingual-e5-large-instruct"
embedder = OpenAIEmbeddings(model=embedding_model, base_url="http://localhost:8080/v1",api_key="EMPTY")

# ================================
# Get chunks with unstructured
def get_article_chunks(file_path):
# Reference: https://docs.unstructured.io/open-source/core-functionality/chunking
    chunks = partition_pdf(
        filename=file_path,
        infer_table_structure=True,            # extract tables
        strategy="hi_res",                     # mandatory to infer tables

        extract_image_block_types=["Image"],   # Add 'Table' to list to extract image of tables
        # image_output_dir_path=output_path,   # if None, images and tables will saved in base64

        extract_image_block_to_payload=True,   # if true, will extract base64 for API usage

        chunking_strategy="by_title",          # or 'basic'
        max_characters=10000,                  # defaults to 500
        combine_text_under_n_chars=2000,       # defaults to 0
        new_after_n_chars=6000,

        # extract_images_in_pdf=True,          # deprecated
    )


    # ================================
    # separate tables from texts
    tables = []
    texts = []

    for chunk in chunks:
        if "Table" in str(type(chunk)):
            tables.append(chunk)

        if "CompositeElement" in str(type((chunk))):
            texts.append(chunk)

    return texts, tables


def summarize_article_data(texts, tables):
    # ================================
    ## Summarize the data
    # Prompt
    prompt_text = """
    You are an assistant tasked with summarizing tables and text.
    Give a concise summary of the table or text.

    Respond only with the summary, no additionnal comment.
    Do not start your message by saying "Here is a summary" or anything like that.
    Just give the summary as it is.

    Table or text chunk: {element}

    """
    prompt = ChatPromptTemplate.from_template(prompt_text)

    # Summary chain
    model = ChatOpenAI(base_url="https://llm.api.cloud.yandex.net/v1",  temperature=0.5, model_name=f"gpt://{folder_id}/qwen3-235b-a22b-fp8/latest")
    summarize_chain = {"element": lambda x: x} | prompt | model | StrOutputParser()


    # Summarize text
    text_summaries = summarize_chain.batch(texts, {"max_concurrency": 3})

    # Summarize tables
    tables_html = [table.metadata.text_as_html for table in tables]
    table_summaries = summarize_chain.batch(tables_html, {"max_concurrency": 3})

    return text_summaries, table_summaries


def get_article_vectorstore(texts, text_summaries, tables, table_summaries):
    # ================================
    # Load data and summaries to vectorstore
    # The vectorstore to use to index the child chunks
    vectorstore = Chroma(collection_name="multi_modal_rag", embedding_function=embedder)

    # The storage layer for the parent documents
    store = InMemoryStore()
    id_key = "doc_id"

    # The retriever (empty to start)
    retriever = MultiVectorRetriever(
        vectorstore=vectorstore,
        docstore=store,
        id_key=id_key,
    )

    # Add texts
    doc_ids = [str(uuid.uuid4()) for _ in texts]
    summary_texts = [
        Document(page_content=summary, metadata={id_key: doc_ids[i]}) for i, summary in enumerate(text_summaries)
    ]
    retriever.vectorstore.add_documents(summary_texts)
    retriever.docstore.mset(list(zip(doc_ids, texts)))

    # Add tables
    table_ids = [str(uuid.uuid4()) for _ in tables]
    summary_tables = [
        Document(page_content=summary, metadata={id_key: table_ids[i]}) for i, summary in enumerate(table_summaries)
    ]
    if summary_tables:
        retriever.vectorstore.add_documents(summary_tables)
        retriever.docstore.mset(list(zip(table_ids, tables)))
    
    return retriever


# # ================================
# # RAG pipeline
# chain = (
#     {
#         "context": retriever | RunnableLambda(parse_docs),
#         "question": RunnablePassthrough(),
#     }
#     | RunnableLambda(build_prompt)
#     | ChatOpenAI(model="gpt-4o-mini")
#     | StrOutputParser()
# )



def get_article_title_info(article_name):
    article_title = article_name.replace("_", " ")

    # Ищем статью в OpenAlex
    article_info = find_article_by_title(article_title)

    # Сохраняем информацию о статье в две папки: article_info (полная) и answers (основные поля)
    article_info_dir = Path("data") / article_name / "article_info"
    article_info_dir.mkdir(parents=True, exist_ok=True)
    
    answers_dir = Path("data") / article_name / "answers"
    answers_dir.mkdir(parents=True, exist_ok=True)

    if article_info:
        print("\n✅ Информация о статье найдена в OpenAlex:")
        print(f"Название: {article_info['title']}")
        print(f"DOI: {article_info['doi'] or 'Не указан'}")
        print(f"Журнал: {article_info['journal_name'] or 'Не указан'}")
        print(f"Дата публикации: {article_info['publication_date'] or 'Не указана'}")
        print(f"Год: {article_info['publication_year'] or 'Не указан'}")
        print(f"Цитирований: {article_info['cited_by_count']}")
        
        # Сохраняем полную информацию в JSON файл
        import json
        info_file = article_info_dir / "openalex_info.json"
        with open(info_file, 'w', encoding='utf-8') as f:
            json.dump(article_info, f, ensure_ascii=False, indent=2)
        print(f"Полная информация сохранена в: {info_file}")
        
        # Сохраняем полные поля в article_info для справки
        fields_to_save_full = {
            'title.txt': article_info['title'],
            'doi.txt': article_info['doi'] or 'Не указан',
            'journal.txt': article_info['journal_name'] or 'Не указан',
            'publication_date.txt': article_info['publication_date'] or 'Не указана',
            'publication_year.txt': str(article_info['publication_year']) if article_info['publication_year'] else 'Не указан',
            'citations.txt': str(article_info['cited_by_count'])
        }
        
        for filename, content in fields_to_save_full.items():
            field_file = article_info_dir / filename
            with open(field_file, 'w', encoding='utf-8') as f:
                f.write(content)
        
        # Сохраняем основные поля в answers папку
        answers_fields = {
            'doi.txt': article_info['doi'] or 'Не указан',
            'journal.txt': article_info['journal_name'] or 'Не указан',
            'date.txt': article_info['publication_date'] or 'Не указана'
        }
        
        for filename, content in answers_fields.items():
            field_file = answers_dir / filename
            with open(field_file, 'w', encoding='utf-8') as f:
                f.write(content)
        
        print("Основные поля сохранены в папку answers")
        print("Полные поля сохранены в папку article_info")
    else:
        print("❌ Информация о статье не найдена в OpenAlex")
        
        # Сохраняем информацию о том, что статья не найдена
        not_found_file = article_info_dir / "not_found.txt"
        with open(not_found_file, 'w', encoding='utf-8') as f:
            f.write(f"Статья с названием '{article_title}' не найдена в OpenAlex")
        print(f"Информация о поиске сохранена в: {not_found_file}")
        
        # Сохраняем заглушки в answers папку
        answers_fields = {
            'doi.txt': 'Не найден',
            'journal.txt': 'Не найден',
            'date.txt': 'Не найдена'
        }
        
        for filename, content in answers_fields.items():
            field_file = answers_dir / filename
            with open(field_file, 'w', encoding='utf-8') as f:
                f.write(content)
        
        print("Заглушки сохранены в папку answers")

    print("\n" + "="*60 + "\n")

