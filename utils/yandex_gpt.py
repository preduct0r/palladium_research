# libraries
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Dict, Any, Optional, Union

import aiohttp
import requests

from colorama import Fore, Style
from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import PromptTemplate

from ..config.config import Config
from ..prompts import generate_subtopics_prompt
from .costs import estimate_llm_cost
from .validators import Subtopics

cfg = Config()


def get_llm(llm_provider, **kwargs):
    from gpt_researcher.llm_provider import GenericLLMProvider
    return GenericLLMProvider.from_provider(llm_provider, **kwargs)


async def _call_yandex_gpt_direct(
    messages: list,
    model: str = "yandexgpt-lite",
    temperature: float = 0.4,
    max_tokens: int = 8000,
    stream: bool = False,
    websocket: Any = None
) -> str:
    """
    Direct HTTP call to YandexGPT API without SDK dependency.
    
    Args:
        messages: List of message dictionaries with 'role' and 'content'
        model: YandexGPT model name 
        temperature: Temperature parameter
        max_tokens: Maximum tokens to generate
        stream: Whether to stream response
        websocket: WebSocket for streaming (if applicable)
        
    Returns:
        str: Response text from YandexGPT
    """
    try:
        # Get credentials from environment
        yc_api_key = os.getenv('YC_API_KEY')
        yc_folder_id = os.getenv('YC_FOLDER_ID')
        
        if not yc_api_key or not yc_folder_id:
            raise ValueError("YandexGPT credentials not found. Set YC_API_KEY and YC_FOLDER_ID environment variables.")
        
        # Convert messages to YandexGPT format
        yandex_messages = []
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            
            # Map roles: assistant -> assistant, system/user -> user
            if role == 'assistant':
                yandex_role = 'assistant'
            else:
                yandex_role = 'user'
                
            yandex_messages.append({
                "role": yandex_role,
                "text": content
            })
        
        # Prepare request data
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Api-Key {yc_api_key}"
        }
        
        # Ensure max_tokens is a valid integer
        if max_tokens is None or max_tokens == "None":
            max_tokens = 8000  # Default value
        
        # Convert to int if it's a string
        if isinstance(max_tokens, str):
            try:
                max_tokens = int(max_tokens)
            except ValueError:
                max_tokens = 8000
        
        # Ensure max_tokens is within reasonable limits
        max_tokens = max(1, min(max_tokens, 8000))
        
        data = {
            "modelUri": f"gpt://{yc_folder_id}/{model}",
            "completionOptions": {
                "stream": stream,
                "temperature": temperature,
                "maxTokens": max_tokens  # Pass as integer, not string
            },
            "messages": yandex_messages
        }
        
        # Debug logging
        logging.debug(f"🔍 YandexGPT request data: {json.dumps(data, ensure_ascii=False, indent=2)}")
        
        if stream and websocket:
            # For streaming, we'll use async approach
            return await _yandex_gpt_stream(headers, data, websocket)
        else:
            # Non-streaming request
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://llm.api.cloud.yandex.net/foundationModels/v1/completion",
                    headers=headers,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        
                        # Debug logging for errors
                        logging.error(f"🚨 YandexGPT error details:")
                        logging.error(f"   Status: {response.status}")
                        logging.error(f"   Error text: {error_text}")
                        logging.error(f"   Request data: {json.dumps(data, ensure_ascii=False, indent=2)}")
                        
                        raise Exception(f"YandexGPT API error {response.status}: {error_text}")
                    
                    # Get raw response text first for debugging
                    raw_response = await response.text()
                    logging.debug(f"🔍 YandexGPT raw response: {raw_response[:500]}...")  # First 500 chars
                    
                    # Handle JSON-lines format (multiple JSON objects separated by newlines)
                    try:
                        # Check if this is a streaming response (multiple JSON objects)
                        if '\n{' in raw_response or raw_response.count('{"result"') > 1:
                            # Parse JSON-lines format - take the last complete JSON object
                            lines = raw_response.strip().split('\n')
                            result = None
                            
                            for line in reversed(lines):  # Start from the last line
                                line = line.strip()
                                if line and line.startswith('{') and line.endswith('}'):
                                    try:
                                        result = json.loads(line)
                                        if 'result' in result and 'alternatives' in result['result']:
                                            break  # Found a valid complete response
                                    except json.JSONDecodeError:
                                        continue
                            
                            if result is None:
                                raise Exception("No valid JSON object found in streaming response")
                        else:
                            # Single JSON object
                            result = json.loads(raw_response)
                    except json.JSONDecodeError as json_error:
                        logging.error(f"❌ JSON parsing failed: {json_error}")
                        logging.error(f"   Raw response: {raw_response}")
                        raise Exception(f"YandexGPT returned invalid JSON: {json_error}")
                    
                    if 'result' not in result or 'alternatives' not in result['result']:
                        logging.error(f"❌ Unexpected YandexGPT response format: {result}")
                        raise Exception(f"Unexpected YandexGPT response format: {result}")
                    
                    response_text = result['result']['alternatives'][0]['message']['text'].strip()
                    
                    if not response_text:
                        raise Exception("YandexGPT returned empty response")
                    
                    # Clean markdown code blocks if present (YandexGPT sometimes wraps JSON in ```json ... ```)
                    if response_text.startswith('```') and response_text.endswith('```'):
                        lines = response_text.split('\n')
                        if len(lines) > 2:
                            # Remove first line (```json or ```) and last line (```)
                            response_text = '\n'.join(lines[1:-1]).strip()
                    
                    logging.info(f"✅ YandexGPT direct API call successful")
                    return response_text
                    
    except Exception as e:
        logging.error(f"❌ YandexGPT direct API call failed: {e}")
        raise


async def _yandex_gpt_stream(headers: dict, data: dict, websocket: Any) -> str:
    """
    Handle streaming response from YandexGPT.
    """
    try:
        # YandexGPT streaming implementation
        data["completionOptions"]["stream"] = True
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://llm.api.cloud.yandex.net/foundationModels/v1/completion",
                headers=headers,
                json=data,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"YandexGPT streaming error {response.status}: {error_text}")
                
                full_response = ""
                paragraph = ""
                
                async for line in response.content:
                    if line:
                        try:
                            line_text = line.decode('utf-8').strip()
                            if line_text.startswith('data: '):
                                json_data = line_text[6:]  # Remove 'data: ' prefix
                                if json_data and json_data != '[DONE]':
                                    chunk = json.loads(json_data)
                                    if 'result' in chunk and 'alternatives' in chunk['result']:
                                        delta = chunk['result']['alternatives'][0]['message']['text']
                                        full_response += delta
                                        paragraph += delta
                                        
                                        # Send chunks via websocket
                                        if "\n" in paragraph:
                                            if websocket:
                                                await websocket.send_json({"type": "report", "output": paragraph})
                                            paragraph = ""
                        except json.JSONDecodeError:
                            continue
                
                # Send remaining paragraph
                if paragraph and websocket:
                    await websocket.send_json({"type": "report", "output": paragraph})
                
                return full_response
                
    except Exception as e:
        logging.error(f"❌ YandexGPT streaming failed: {e}")
        raise


async def create_chat_completion(
        messages: list,  # type: ignore
        model: Optional[str] = None,
        temperature: Optional[float] = 0.4,
        max_tokens: Optional[int] = 8000,
        llm_provider: Optional[str] = None,
        stream: Optional[bool] = False,
        websocket: Any | None = None,
        llm_kwargs: Dict[str, Any] | None = None,
        cost_callback: callable = None,
        reasoning_effort: Optional[str] = "low"
) -> str:
    """Create a chat completion using the OpenAI API
    Args:
        messages (list[dict[str, str]]): The messages to send to the chat completion
        model (str, optional): The model to use. Defaults to None.
        temperature (float, optional): The temperature to use. Defaults to 0.4.
        max_tokens (int, optional): The max tokens to use. Defaults to 4000.
        stream (bool, optional): Whether to stream the response. Defaults to False.
        llm_provider (str, optional): The LLM Provider to use.
        webocket (WebSocket): The websocket used in the currect request,
        cost_callback: Callback function for updating cost
    Returns:
        str: The response from the chat completion
    """
    # validate input
    if model is None:
        raise ValueError("Model cannot be None")
    if max_tokens is not None and max_tokens > 16001:
        raise ValueError(
            f"Max tokens cannot be more than 16,000, but got {max_tokens}")

    # Special handling for YandexGPT using direct HTTP calls
    if llm_provider == "yandex":
        logging.info(f"🔄 Using direct YandexGPT API for model: {model}")
        
        try:
            response = await _call_yandex_gpt_direct(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
                websocket=websocket
            )
            
            if cost_callback:
                llm_costs = estimate_llm_cost(str(messages), response)
                cost_callback(llm_costs)
            
            return response
            
        except Exception as e:
            logging.error(f"❌ YandexGPT direct call failed: {e}")
            raise RuntimeError(f"Failed to get response from YandexGPT direct API: {e}")

    # Standard processing for all other providers
    # Get the provider from supported providers
    kwargs = {
        'model': model,
        **(llm_kwargs or {})
    }

    if 'o3' in model or 'o1' in model:
        kwargs['reasoning_effort'] = reasoning_effort
    else:
        kwargs['temperature'] = temperature
        kwargs['max_tokens'] = max_tokens
    print(kwargs)
    
    try:
        provider = get_llm(llm_provider, **kwargs)
    except Exception as e:
        logging.error(f"Failed to create LLM provider {llm_provider}: {e}")
        raise RuntimeError(f"Failed to create LLM provider {llm_provider}: {e}")
    
    response = ""
    # create response
    for _ in range(10):  # maximum of 10 attempts
        try:
            response = await provider.get_chat_response(
                messages, stream, websocket
            )
            
            # Проверяем что response не None и не пустой
            if response is None:
                logging.error(f"LLM provider {llm_provider} returned None response")
                continue
            
            if response == "":
                logging.warning(f"LLM provider {llm_provider} returned empty response")
                continue
            
            if cost_callback:
                llm_costs = estimate_llm_cost(str(messages), response)
                cost_callback(llm_costs)

            return response
            
        except Exception as e:
            logging.error(f"Error during LLM call attempt: {e}")
            continue

    logging.error(f"Failed to get response from {llm_provider} API after 10 attempts")
    raise RuntimeError(f"Failed to get response from {llm_provider} API after 10 attempts")