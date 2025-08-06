
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from base64 import b64decode
from pathlib import Path

def parse_docs(docs):
    """Split base64-encoded images and texts"""
    b64 = []
    text = []
    for doc in docs:
        try:
            b64decode(doc)
            b64.append(doc)
        except Exception as e:
            text.append(doc)
    return {"images": b64, "texts": text}


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
    
    # Check and read files only if they exist
    idea = ""
    technology = ""
    tematic = ""
    
    if (answers_dir / "idea.txt").exists():
        with open(answers_dir / "idea.txt", encoding='utf-8') as f:
            idea = f.read()
    
    if (answers_dir / "technology.txt").exists():
        with open(answers_dir / "technology.txt", encoding='utf-8') as f:
            technology = f.read()
    
    if (answers_dir / "tematic.txt").exists():
        with open(answers_dir / "tematic.txt", encoding='utf-8') as f:
            tematic = f.read()
    
    user_question = kwargs["question"]

    # Build user_request conditionally based on available files
    user_request_parts = [f"Вопрос: {user_question}"]
    
    if technology:
        user_request_parts.append(f"Технология: {technology}")
    
    if tematic:
        user_request_parts.append(f"Тематика: {tematic}")
    
    if idea:
        user_request_parts.append(f"Идея: {idea}")
    
    user_request = ". ".join(user_request_parts)

    neuro_response = kwargs["neuro"]

    context_text = ""
    if len(docs_by_type["texts"]) > 0:
        for text_element in docs_by_type["texts"]:
            context_text += text_element.text

    # construct prompt with context (including images)
    prompt_template = f"""
    Answer the question based on the following context with information from the article we are researching. Also be free to use the information from the neuro response, which consist of the information from the internet, which can be useful for answering the question, but context from the article is more important.
    Context: {context_text}
    Question: {user_request}
    Yandex_search_response: {neuro_response}
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
            HumanMessage(content=),
        ]
    )






