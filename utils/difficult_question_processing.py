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

load_dotenv()

# GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY")
# Convert tracing flag to boolean
LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() in ("true", "1", "yes")

OPENAI_API_KEY = os.getenv("YANDEX_API_KEY")
folder_id = os.getenv("YANDEX_FOLDER_ID")

# _embeddings = GigaChatEmbeddings(model = "EmbeddingsGigaR",credentials= os.environ.get("GIGACHAT_CREDENTIALS"),scope =os.environ.get("GIGACHAT_API_CORP") , verify_ssl_certs = False)
embedder = OpenAIEmbeddings(model=os.getenv("EMBEDDING_MODEL"), base_url=os.getenv("EMBEDDING_BASE_URL") ,api_key=os.getenv("EMBEDDING_API_KEY"))

chroma_vector_store = Chroma(collection_name="relevant_data", embedding_function=embedder)

with open("prompts/get_keywords.txt") as f:
    serp_prompt_template = f.read()
with open("prompts/get_search_query.txt") as f:
    search_query_template = f.read()
model = ChatOpenAI(base_url="https://llm.api.cloud.yandex.net/v1",  temperature=0.5, model_name=f"gpt://{folder_id}/qwen3-235b-a22b-fp8/latest")



def download_relevant_pdfs(questions_demands_search, article_name):
    # Читаем ответы из новых файлов
    answers_dir = Path("data") / article_name / "answers"
    
    with open(answers_dir / "idea.txt", encoding='utf-8') as f:
        idea = f.read()
    with open(answers_dir / "technology.txt", encoding='utf-8') as f:
        technology = f.read()
    with open(answers_dir / "tematic.txt", encoding='utf-8') as f:
        tematic = f.read()
    
    all_keywords = set()
    chunks = set()

    for question in questions_demands_search:
        serp_prompt = serp_prompt_template.replace("<QUESTION>", question).replace("<IDEA>", idea).replace("<TECHNOLOGY>", technology).replace("<TEMATIC>", tematic)
        serp_chain = ChatPromptTemplate.from_template(serp_prompt) | model | StrOutputParser()
        # The prompt is already fully formed, so we pass an empty dictionary to invoke.
        raw_keywords = serp_chain.invoke({})
        
        # Очищаем результат от лишнего текста и получаем только ключевые слова
        keywords = raw_keywords.strip()
        # Удаляем возможные префиксы типа "Keywords:", "Answer:", etc.
        keywords = re.sub(r'^[^:]*:\s*', '', keywords)
        # Удаляем лишние пробелы и переносы строк
        keywords = re.sub(r'\s+', ' ', keywords).strip()
        
        print(f"Вопрос: {question}")
        print(f"Ключевые слова: {keywords}")
        try:
            all_keywords.update(keywords.split(", "))
        except:
            print(f"Ошибка при обновлении множества: {keywords}")

        # ================================
        # query = f"Технология: {technology}. {question}"
        query = question.replace("<технология>", technology).lower()
        yandex_snippets = YandexSearch(query).extract_yandex_snippets()
        chunks.update(yandex_snippets)

        # ================================
        # extract_serpapi_pdfs(query, article_name=article_name)

    all_keywords = [x for x in list(all_keywords) if len(x.split(" "))>1] + ["палладий"]

    # Переводим ключевые слова на английский для более эффективного поиска в OpenAlex
    print("\n=== Перевод ключевых слов для поиска в OpenAlex ===")
    translated_keywords = translate_keywords(list(all_keywords))
    

    seen_titles = set()
    for keyword in all_keywords + translated_keywords:
        openalex_results = extract_openalex_pdfs(keyword, article_name=article_name, seen_titles=seen_titles)


    
    # Поиск по переведенным ключевым словам в OpenAlex
    for translated_keyword in translated_keywords:
        if translated_keyword and translated_keyword.strip():
            print(f"Поиск в OpenAlex по переведенному ключевому слову: {translated_keyword}")
            openalex_results = extract_openalex_pdfs(translated_keyword, article_name=article_name)

    return chunks, all_keywords


def get_relevant_data_chunks(file_dir):
    # Reference: https://docs.unstructured.io/open-source/core-functionality/chunking
    
    # Найти все PDF файлы в папке и подпапках
    pdf_files = []
    file_dir_path = Path(file_dir)
    
    # Рекурсивно найти все PDF файлы
    for pdf_file in file_dir_path.rglob("*.pdf"):
        pdf_files.append(pdf_file)
    
    print(f"Найдено {len(pdf_files)} PDF файлов в папке {file_dir}")
    
    all_texts = []
    
    # Обработать каждый PDF файл
    for pdf_file in pdf_files:
        print(f"Обработка файла: {pdf_file}")
        try:
            chunks = partition_pdf(
                filename=str(pdf_file),         # disable table extraction
                strategy="ocr_only",            # mandatory for better text extraction
                languages=["ru", "en"],                   

                # Remove image extraction parameters
                # extract_image_block_types=["Image"],   # disabled - no images
                # extract_image_block_to_payload=True,   # disabled - no images

                chunking_strategy="by_title",          # or 'basic'
                max_characters=1000,                  # defaults to 500
                combine_text_under_n_chars=500,       # defaults to 0

                # extract_images_in_pdf=True,          # deprecated
            )

            # ================================
            # extract only text chunks
            texts = []

            for chunk in chunks:
                # Only keep text elements, skip tables and images
                if "CompositeElement" in str(type(chunk)) or "NarrativeText" in str(type(chunk)) or "Title" in str(type(chunk)):
                    texts.append(chunk)
            
            all_texts.extend(texts)
            print(f"Извлечено {len(texts)} текстовых чанков из {pdf_file}")
            
        except Exception as e:
            print(f"Ошибка при обработке файла {pdf_file}: {e}")
            continue

    print(f"Всего извлечено {len(all_texts)} текстовых чанков из всех файлов")
    return all_texts  # Return only texts, no tables



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