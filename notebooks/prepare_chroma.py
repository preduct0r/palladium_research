#!/usr/bin/env python3
"""
Скрипт для создания ChromaDB из файла ice_creame_data.txt
"""

import os
from langchain_community.vectorstores import Chroma
from langchain.embeddings import OpenAIEmbeddings
from langchain.schema import Document

# Конфигурация
CHROMA_DB_PATH = "chroma_db_ice_creame"
COLLECTION_NAME = "ice_creame"
DATA_FILE = "notebooks/ice_creame_data.txt"

# Инициализация эмбеддера (тот же что используется в open_chroma.py)
embedder = OpenAIEmbeddings(
    model="Qwen/Qwen3-Embedding-8B", 
    base_url="http://localhost:8100/v1",
    api_key="EMPTY"
)

def load_data_from_file(file_path: str):
    """Загружает данные из текстового файла"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Файл не найден: {file_path}")
    
    print(f"📂 Загружаем данные из: {file_path}")
    
    documents = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if line:  # Пропускаем пустые строки
                # Создаем документ для каждой строки
                doc = Document(
                    page_content=line,
                    metadata={
                        "source": file_path,
                        "line_number": line_num,
                        "doc_id": f"line_{line_num}"
                    }
                )
                documents.append(doc)
    
    print(f"📊 Загружено строк: {len(documents)}")
    return documents

def create_chroma_db(documents):
    """Создает ChromaDB из документов"""
    print(f"🔧 Создаем ChromaDB в: {CHROMA_DB_PATH}")
    print(f"📁 Коллекция: {COLLECTION_NAME}")
    
    # Удаляем существующую базу если она есть
    if os.path.exists(CHROMA_DB_PATH):
        print(f"⚠️  Удаляем существующую базу: {CHROMA_DB_PATH}")
        import shutil
        shutil.rmtree(CHROMA_DB_PATH)
    
    # Создаем векторное хранилище
    vectorstore = Chroma.from_documents(
        documents=documents,
        embedding=embedder,
        collection_name=COLLECTION_NAME,
        persist_directory=CHROMA_DB_PATH
    )
    
    # Сохраняем базу
    vectorstore.persist()
    
    # Проверяем количество документов
    count = vectorstore._collection.count()
    print(f"✅ База создана! Документов в базе: {count}")
    
    return vectorstore

def test_search(vectorstore):
    """Тестирует поиск в созданной базе"""
    print("\n🔍 Тестируем поиск...")
    
    test_queries = [
        "джелато",
        "мороженое итальянское",
        "палладий аффинаж"
    ]
    
    for query in test_queries:
        print(f"\n📝 Запрос: '{query}'")
        results = vectorstore.similarity_search(query, k=3)
        print(f"Найдено результатов: {len(results)}")
        
        for i, doc in enumerate(results, 1):
            print(f"  {i}. {doc.page_content[:100]}...")

if __name__ == "__main__":
    print("🚀 Запуск создания ChromaDB для ice_creame данных")
    
    try:
        # Загружаем данные
        documents = load_data_from_file(DATA_FILE)
        
        # Создаем базу
        vectorstore = create_chroma_db(documents)
        
        # Тестируем
        test_search(vectorstore)
        
        print(f"\n🎉 Готово! ChromaDB создана в папке: {CHROMA_DB_PATH}")
        print(f"Коллекция: {COLLECTION_NAME}")
        print(f"Документов: {len(documents)}")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        raise
