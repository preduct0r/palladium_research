import os
from langchain_community.embeddings.gigachat import GigaChatEmbeddings
from dotenv import load_dotenv      
from langchain_community.vectorstores import Chroma
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
import uuid
from langchain_core.prompts import ChatPromptTemplate
import re
from langchain.schema.document import Document

from utils.yandex_gpt import yandex_gpt_request
from retrievers._serpapi import extract_serpapi_pdfs
from retrievers.yandex_search import YandexSearch
from retrievers.openalex import extract_openalex_pdfs
from pathlib import Path
from unstructured.partition.pdf import partition_pdf
from langchain.embeddings import OpenAIEmbeddings

from utils.yandex_gpt import translate_keywords
from retrievers.neuro import get_neuro_response
load_dotenv()

# Конфигурация
CHROMA_DB_PATH = "chroma_db"
COLLECTION_NAME = "relevant_data"

embedder = OpenAIEmbeddings(model=os.getenv("EMBEDDING_MODEL"), base_url=os.getenv("EMBEDDING_BASE_URL") ,api_key=os.getenv("EMBEDDING_API_KEY"))


def load_chroma_db():
    """Загружает существующую ChromaDB базу"""
    if not os.path.exists(CHROMA_DB_PATH):
        raise ValueError(f"База данных не найдена: {CHROMA_DB_PATH}")
    
    print(f"📂 Загружаем ChromaDB из: {CHROMA_DB_PATH}")
    
    vectorstore = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embedder,
        persist_directory=CHROMA_DB_PATH
    )
    
    # Проверяем количество документов
    count = vectorstore._collection.count()
    print(f"📊 Загружено документов: {count}")
    
    return vectorstore


def search_query(vectorstore, query: str, k: int = 5):
    """Выполняет поиск по запросу"""
    print(f"\n🔍 Запрос: '{query}'")
    
    retriever = vectorstore.as_retriever(search_kwargs={"k": k})
    results = retriever.get_relevant_documents(query)
    
    print(f"✅ Найдено результатов: {len(results)}")
    print("=" * 60)
    
    for i, doc in enumerate(results, 1):
        print(f"\n{i}. Score: {doc.metadata.get('score', 'N/A')}")
        print(f"Source: {doc.metadata.get('source', 'N/A')}")
        print(f"Content: {doc.page_content[:2000]}...")
    
    return results


def get_relevant_data_vectorstore(texts):
    """
    Creates a vector store for relevant data using simple Chroma vectorstore.
    Indexes full text chunks directly for retrieval.
    """
    # ================================
    # Create vectorstore for full text chunks
    vectorstore = Chroma(collection_name="relevant_data", embedding_function=embedder)
    
    # Convert text chunks to Document objects
    documents = []
    for i, text_chunk in enumerate(texts):
        # Extract text content from unstructured elements
        if hasattr(text_chunk, 'text'):
            content = text_chunk.text
        else:
            content = str(text_chunk)
        
        # Create Document with metadata
        doc = Document(
            page_content=content,
            metadata={
                "chunk_id": i,
                "source": "pdf_chunk"
            }
        )
        documents.append(doc)
    
    # Add documents to vectorstore
    vectorstore.add_documents(documents)
    
    # Return retriever
    return vectorstore.as_retriever(search_kwargs={"k": 10})