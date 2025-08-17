
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from base64 import b64decode
from pathlib import Path

def parse_docs(docs):
    """Split base64-encoded images and texts"""
    text = []
    for doc in docs:
        text.append(doc)
    return {"texts": text}


def build_prompt(kwargs):

    docs_by_type = kwargs["context"]
    user_question = kwargs["question"]

    context_text = ""
    if len(docs_by_type["texts"]) > 0:
        for text_element in docs_by_type["texts"]:
            context_text += text_element.text

    # construct prompt with context (including images)
    prompt_template = f"""
    Answer the question based only on the following context, which can include text, tables, and the below image.
    Context: {context_text}
    Question: {user_question}
    """

    prompt_content = [{"type": "text", "text": prompt_template}]

    if len(docs_by_type["images"]) > 0:
        for image in docs_by_type["images"]:
            prompt_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image}"},
                }
            )

    return ChatPromptTemplate.from_messages(
        [
            HumanMessage(content=prompt_content),
        ]
    )


def build_prompt3(kwargs):
    docs_by_type = kwargs["context"]

    answers_dir = Path("data") / kwargs["article_name"] / "answers"
    
    if (answers_dir / "idea.txt").exists():
        with open(answers_dir / "idea.txt", encoding='utf-8') as f:
            idea = f.read()
    
    if (answers_dir / "technology.txt").exists():
        with open(answers_dir / "technology.txt", encoding='utf-8') as f:
            technology = f.read()
    
    neuro_response = kwargs["neuro"]

    context_text = ""
    if len(docs_by_type["texts"]) > 0:
        for text_element in docs_by_type["texts"]:
            context_text += text_element.text

    # construct prompt with context (including images)
    prompt_template = f"""
    Answer the question based on the following context with information from the article we are researching. Also feel free to use information from the Yandex search response, which consists of information from the internet that can be useful for answering the question, but context from the article is more important.
    Context: {context_text}
    """

    # if technology:
    #     prompt_template += f"\nТехнология в статье: {technology}"
    
    # if idea:
    #     prompt_template += f"\nИдея в статье: {idea}"

    user_question = kwargs["question"]

    user_request_part = f"Question: {user_question}" 
    
    if user_question not in ["Напиши одним предложением о какой промышленной технологии идет речь в этой статье. Выведи только название технологии, ничего больше, ответ должен содержать от 4 до 15 слов", "Какова основная идея изложенна в статье?", "Какое направление, тематика у этой статьи? Выведи только тематики ничего больше. Например: 'Катализ, палладий, деароматизация, нефтехимия, каталитическая переработка'"]:
        prompt_template += f"\nYandex_search_response: {neuro_response}"
        
    prompt_template += user_request_part

    if user_question not in ["Напиши одним предложением о какой промышленной технологии идет речь в этой статье. Выведи только название технологии, ничего больше, ответ должен содержать от 4 до 15 слов", "Какое направление, тематика у этой статьи? Выведи только тематики ничего больше. Например: 'Катализ, палладий, деароматизация, нефтехимия, каталитическая переработка'"]:
        prompt_template += "\nЕсли в статье нет информации, попробуй поразмышлять на основе знаний, которые у тебя есть."
        
    # if len(kwargs["options"]) > 0:
    #     prompt_template += f"\nОтвет должен содержать только один из вариантов и ничего больше: {kwargs['options']}"
    # else:
    #     prompt_template += "\nОтвет должен быть не больше 3 предложений"

    prompt_content = [{"type": "text", "text": prompt_template}]

    if len(docs_by_type["images"]) > 0:
        for image in docs_by_type["images"]:
            prompt_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image}"},
                }
            )

    return ChatPromptTemplate.from_messages(
        [
            HumanMessage(content=prompt_content),
        ]
    )


# ===========================================================
def build_prompt4(kwargs):
    original_article_data = kwargs["original_article_data"]['texts'][0].text
    
    neuro_response = kwargs["neuro"]

    # construct prompt with context (including images)
    prompt_template = f"""Answer the question based on the following original article we are researching. Feel free to use information from the Yandex search response, which consists of information from the internet that can be useful for answering the question. Also use information from the relevant data, which consists of information from another articles in the same domain. But remember that data from the original article is key for answering the question, other is just supplement information
    Original article: {original_article_data}
    """
    user_question = kwargs["question"]
    user_request_part = f"Question: {user_question}" 


    
    if user_question not in ["Напиши одним предложением о какой промышленной технологии идет речь в этой статье. Выведи только название технологии, ничего больше, ответ должен содержать от 4 до 15 слов", "Какова основная идея изложенна в статье?", "Какое направление, тематика у этой статьи? Выведи только тематики ничего больше. Например: 'Катализ, палладий, деароматизация, нефтехимия, каталитическая переработка'"]:
        prompt_template += f"\nYandex_search_response: {neuro_response}"

        relevant_data = kwargs["relevant_data"]
        relevant_data_text = ""
        if len(relevant_data["texts"]) > 0:
            for text_element in relevant_data["texts"]:
                relevant_data_text += text_element.page_content + "\n"
        prompt_template += f"\nRelevant data: {relevant_data_text}"
            
    prompt_template += user_request_part

    if user_question not in ["Напиши одним предложением о какой промышленной технологии идет речь в этой статье. Выведи только название технологии, ничего больше, ответ должен содержать от 4 до 15 слов", "Какое направление, тематика у этой статьи? Выведи только тематики ничего больше. Например: 'Катализ, палладий, деароматизация, нефтехимия, каталитическая переработка'", "Какова основная идея изложенна в статье?"]:
        prompt_template += "\nЕсли в статье нет информации, попробуй поразмышлять на основе знаний, которые у тебя есть."
    
    # ================================
    if len(kwargs["options"]) > 0:
        prompt_template += f"\nОтвет должен содержать только один из вариантов и ничего больше: {kwargs['options']}"
    elif user_question not in ["Напиши одним предложением о какой промышленной технологии идет речь в этой статье. Выведи только название технологии, ничего больше, ответ должен содержать от 4 до 15 слов", "Какова основная идея изложенна в статье?", "Какое направление, тематика у этой статьи? Выведи только тематики ничего больше. Например: 'Катализ, палладий, деароматизация, нефтехимия, каталитическая переработка'"]:
        prompt_template += "\nОтвет должен быть не больше 3 предложений"

    if user_question == "Оцени каким может быть потенциальное потребление палладия по миру при условии внедрения подхода из статьи в промышленность?":    
        prompt_template += "\nВ ответе укажи только массу в кг, ничего больше"

    prompt_content = [{"type": "text", "text": prompt_template}]

    return ChatPromptTemplate.from_messages(
        [
            HumanMessage(content=prompt_content),
        ]
    )



