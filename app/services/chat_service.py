import requests
import logging

from schemas.responses import ChatCompletedReponse
from schemas.requests import RequestPayload, ChatMessage
from services.chat_storage_service import get_conv
from app_logging import log
from config import get_settings

from typing import Any
from fastapi import HTTPException
from pydantic import ValidationError

config = get_settings()

def get_system_prompt() -> ChatMessage | None:
    try:
        with open(config.SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
            system_prompt = {"role": "system", "content": f.read().strip()}
            return ChatMessage.model_validate(system_prompt)
    except Exception as e:
        if isinstance(e, ValidationError):
            log(f"System prompt is invalid: {e}", level=logging.ERROR)
        else:
            log(f"Error reading system prompt file: {e}", level=logging.ERROR)
    
    return None

def filter_completed_response_messages(input : list[ChatCompletedReponse | ChatMessage]) -> list[ChatMessage]:
    # Keep all turns, including system prompts and images, in their stored order.
    messages : list[ChatMessage] = []
    for item in input:
        if isinstance(item, ChatMessage):
            messages.append(item)
        elif item.choices:
            messages.append(ChatMessage.model_validate(item.choices[0].message.model_dump()))
    return messages

def create_request_payload(input: ChatMessage, conv_id: int) -> RequestPayload:
    context = filter_completed_response_messages(get_conv(conv_id))
    context.append(input)
    return RequestPayload(
        model = config.MODEL,
        messages = context,
        modalities = config.OUTPUT_MODALITIES,
    )

def send_request_to_openrouter(payload : RequestPayload) -> dict[Any, Any] | None:
    settings = get_settings()

    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.API_KEY.get_secret_value()}"},
            json=payload.model_dump(exclude_none=True),
            timeout=180,
        )
        response.raise_for_status()
        return response.json()
    except requests.Timeout as exc:
        raise HTTPException(status_code=504, detail="The model timed out. Please try again.") from exc
    except (requests.RequestException, ValueError) as exc:
        log("OpenRouter request failed", level=logging.ERROR)
        raise HTTPException(status_code=502, detail="The model request failed. Check the server configuration and try again.") from exc
