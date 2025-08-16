#!/usr/bin/env python3
"""
Простой скрипт для загрузки и тестирования ChromaDB
"""

import os
from langchain_community.vectorstores import Chroma
from langchain.embeddings import OpenAIEmbeddings

# Конфигурация
CHROMA_DB_PATH = "chroma_db"
COLLECTION_NAME = "relevant_data"

# Инициализация эмбеддера (такой же как при создании базы)
embedder = OpenAIEmbeddings(
    model="Qwen/Qwen3-Embedding-8B", 
    base_url="http://localhost:8100/v1",
    api_key="EMPTY"
)

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

if __name__ == "__main__":
    # Загружаем базу
    vectorstore = load_chroma_db()
    
    # Тестовые запросы
    test_queries = [
        # "Gold miners experiencing palladium shortage",
        "Biological activity of cells",
        # "palladium processing",
        # "металлургия палладия",
        # "extraction methods"
    ]
    
    for query in test_queries:
        search_query(vectorstore, query, k=3)
        print("\n" + "="*300 + "\n")
    
    # # Интерактивный режим
    # print("💬 Интерактивный режим (введите 'quit' для выхода):")
    # while True:
    #     # user_query = input("\nВаш запрос: ").strip()
    #     if user_query.lower() in ['quit', 'exit', 'q']:
    #         break
    #     if user_query:
    #         search_query(vectorstore, user_query, k=5)
