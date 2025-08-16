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

from utils.rag import parse_docs, build_prompt4
from utils.initial_article_processing import get_article_chunks, summarize_article_data, get_article_vectorstore, get_article_title_info
from utils.difficult_question_processing import download_relevant_pdfs_and_chunks, get_relevant_data_chunks, get_relevant_data_vectorstore
from retrievers.neuro import get_neuro_response, get_guery
from utils.relevant_data_retrieval import load_chroma_db, search_query
from utils.pdf_parser import parse_single_pdf
from dotenv import load_dotenv, find_dotenv
# ================================
# Load environment variables from the nearest .env file
dotenv_path = find_dotenv()
if not dotenv_path:
    raise FileNotFoundError("'.env' file not found. Please create one in the project root.")
load_dotenv(dotenv_path)


def parse_article_pdf(article_path):
    """
    Парсит PDF статьи и возвращает данные в формате, ожидаемом build_prompt4
    """
    try:
        text, metadata, images, used_ocr = parse_single_pdf(str(article_path))
        
        # Создаем объекты в формате, который ожидает build_prompt4
        class TextElement:
            def __init__(self, text_content):
                self.text = text_content
        
        # Формируем список текстовых элементов
        texts = []
        if text:
            texts.append(TextElement(text))
        
        # Формируем список изображений (base64)
        b64_images = []
        if images:
            for image in images:
                # Если изображения уже в base64 формате, добавляем их
                if isinstance(image, str):
                    b64_images.append(image)
        
        return {"texts": texts, "images": b64_images}
    
    except Exception as e:
        print(f"Ошибка при парсинге PDF {article_path}: {e}")
        # Возвращаем пустую структуру в случае ошибки
        return {"texts": [], "images": []}


for article_path in Path(os.getenv("ARTICLE_DIR")).glob("*.pdf"):
    OPENAI_API_KEY = os.getenv("YANDEX_API_KEY")
    folder_id = os.getenv("YANDEX_FOLDER_ID")
    model = ChatOpenAI(base_url="https://llm.api.cloud.yandex.net/v1",  temperature=0.5, model_name=f"gpt://{folder_id}/qwen3-235b-a22b-fp8/latest")

    article_name = Path(article_path).stem.replace(" ", "_")

    # ================================
    # Создаем функцию-обертку для нейро запросов
    def get_neuro_with_query(question):
        """
        Обертка для get_neuro_response, которая использует get_guery для обработки вопроса
        """
        processed_query = get_guery(question, article_name)
        return get_neuro_response(processed_query)

    # ================================
    # Извлечение информации о статье из OpenAlex
    print("Извлекаем информацию о статье из OpenAlex...")
    get_article_title_info(article_name)

    parse_article_pdf(article_path)
    original_article_data = parse_article_pdf(article_path)['texts'][0].text

    relevant_data_retriever = load_chroma_db().as_retriever(search_kwargs={"k": 5})
    # Создаем папку для сохранения ответов
    answers_dir = Path("data") / article_name / "answers"
    answers_dir.mkdir(parents=True, exist_ok=True)

    questions_and_files = [   
        ("Напиши одним предложением о какой промышленной технологии идет речь в этой статье. Выведи только название технологии, ничего больше, ответ должен содержать от 4 до 15 слов", "technology.txt", ""),
        ("Какова основная научная идея изложенна в статье?", "idea.txt", ""),
        ("Какое направление, тематика у этой статьи? Выведи только тематики ничего больше. Например: 'Катализ, палладий, деароматизация, нефтехимия, каталитическая переработка'", "tematic.txt", ""),
        ("Какой тип у этого проекта?", "type.txt", "прикладной краткосрочный, прикладной среднесрочный, прикладной долгосрочный, фундаментальный"),
        ("Оцени каким может быть потенциальное потребление палладия по миру при условии внедрения подхода из статьи в промышленность?", "potential_consumption.txt", ""),
        ("Какой уровень развития технологии подхода из статьи?", "technology_development_level.txt", "Не индустриализовано, Активно развивается, Полностью индустриализовано"),
        ("Какова новизна применения палладия при применении подхода из статьи?", "palladium_novelty.txt", "Присутствует, Отсутствует"),
        ("Какова научно-техническая реализуемость внедрения палладия при применении подхода из статьи?", "technical_feasibility.txt", "Высокая, Средняя, Низкая, Отсутствует"),
        ("Есть ли коммерческий потенциал внедрения палладия при применении подхода из статьи?", "commercial_potential.txt", "Есть, Нет"),
        ("Каковы конкурентные преимущества палладия в подходе из статьи?", "competitive_advantages.txt", "Высокие, Средние, Низкие, Отсутствуют"),
        ("Какой уровень готовности подхода из статьи с палладием?", "technology_readiness_level.txt", "Идея, Лаборатория, Прототип, Пилотирование, Индустриализовано"),
        ("Какова перспективность рынка для разработки подхода из статьи?", "market_prospects.txt", "Высокая, Средняя, Низкая"),
        ("Какой уровень рыночного коммерческого потенциала для реализации подхода из статьи?", "market_commercial_potential.txt", "Отсутствует, Теоретический интерес, Потенциальный рыночный интерес, Начальная рыночная привлекательность, Подтвержденный интерес рынка, Растущий спрос, Коммерческий запуск, Массовый рынок"),
        ("Какова сложность разработки технологии подхода из статьи?", "development_complexity.txt", "Высокая, Средняя, Низкая"),
        ("Какова сложность внедрения технологии подхода из статьи?", "implementation_complexity.txt", "Высокая, Средняя, Низкая"),
        ("Как ты оцениваешь потенциал коммерциализации подхода из статьи?", "commercialization_potential.txt", "Высокая, Средняя, Низкая"),
        ("Какова предполагаемая длительность разработки технологии по подходу из статьи? ", "development_duration.txt", "< 6 месяцев, < 1 года, < 3 лет, < 5 лет, > 5 лет"),
        ("Стоит ли взять в работу подход из статьи?", "decision.txt", "Взять в проработку, Отложить, Не рассматривать"),
        ("Оставь свои комментарии по поводу подхода из статьи? В комментариях укажи по каким моментам информация тебе кажется неполной или противоречивой", "comments.txt", ""),
    ]



    for question, filename, options in questions_and_files:
        chain_with_sources = {
            "original_article_data": RunnableLambda(lambda _: {"texts": [type('TextElement', (), {'text': original_article_data})()]}),
            "relevant_data": relevant_data_retriever | RunnableLambda(parse_docs),
            "neuro": RunnableLambda(get_neuro_with_query),
            "question": RunnablePassthrough(),
            "article_name": RunnableLambda(lambda _: article_name),
            "options": RunnableLambda(lambda _: options)
        } | RunnablePassthrough().assign(
            response=(
                RunnableLambda(build_prompt4)
                | model
                | StrOutputParser()
            )
        )
        response = chain_with_sources.invoke(question)

        print("Response:", response['response'])
        
        # Сохраняем ответ в файл
        file_path = answers_dir / filename
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(response['response'])
        print(f"Ответ сохранен в: {file_path}")

