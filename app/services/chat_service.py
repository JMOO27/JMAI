import requests
import logging
import re
import time
from functools import lru_cache
from urllib.parse import quote
from uuid import uuid4

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

@lru_cache(maxsize=64)
def get_model_output_modalities(model: str) -> tuple[str, ...]:
    # Cache public model capabilities; never send conversation content to discovery.
    try:
        response = requests.get(
            f"https://openrouter.ai/api/v1/models/{quote(model, safe='/')}/endpoints",
            timeout=15,
        )
        response.raise_for_status()
        return tuple(response.json()["data"]["architecture"]["output_modalities"])
    except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError):
        log("OpenRouter model discovery failed; using chat mode. Set OPENROUTER_API_MODE=images for an image-only model.", level=logging.WARNING)
        return ()


def message_text(message: ChatMessage) -> str:
    if isinstance(message.content, str):
        return message.content
    return "\n".join(part.text for part in message.content or [] if part.type == "text")


def message_images(message: ChatMessage) -> list[dict]:
    content = message.content if isinstance(message.content, list) else []
    images = [part.model_dump() for part in content if part.type == "image_url"]
    images.extend(image.model_dump() for image in message.images or [])
    return images


def create_image_payload(payload: RequestPayload) -> dict:
    latest = payload.messages[-1]
    body = {
        "model": payload.model,
        "prompt": message_text(latest).strip() or "Create an image based on the reference images.",
    }
    # Prefer current uploads; otherwise use the last image for follow-up edits.
    references = message_images(latest)
    if not references:
        for message in reversed(payload.messages[:-1]):
            references = message_images(message)
            if references:
                break
    if references:
        body["input_references"] = references
    return body


def image_response_to_completion(result: dict, model: str) -> dict:
    images = []
    for item in result.get("data", []):
        url = item.get("url")
        if item.get("b64_json"):
            media_type = item.get("media_type") or "image/png"
            url = f"data:{media_type};base64,{item['b64_json']}"
        if url:
            images.append({"type": "image_url", "image_url": {"url": url}})
    if not images:
        raise HTTPException(status_code=502, detail="OpenRouter returned no generated images.")
    # Preserve the existing API contract, storage, and frontend image renderer.
    return {
        "id": result.get("id") or f"image-{uuid4().hex}",
        "object": "chat.completion",
        "created": result.get("created") or int(time.time()),
        "model": model,
        "choices": [{"index": 0, "finish_reason": "stop", "message": {
            "role": "assistant", "content": None, "images": images,
        }}],
        "usage": result.get("usage"),
    }


def provider_error_message(result: dict, payload: RequestPayload, api_key: str) -> str:
    error = result.get("error", {})
    message = error.get("message") if isinstance(error, dict) else None
    if not isinstance(message, str):
        return "The provider rejected the request. Check the model, credentials, and account credits."
    # Keep diagnostics useful without logging keys, prompts, images, or raw metadata.
    if api_key:
        message = message.replace(api_key, "[redacted]")
    for chat in payload.messages:
        text = message_text(chat).strip()
        if text:
            message = message.replace(text, "[message omitted]")
    message = re.sub(r"data:image/[^\s\"']+", "[image omitted]", message)
    return " ".join(message.split())[:500]


def send_request_to_openrouter(payload: RequestPayload) -> dict[Any, Any]:
    settings = get_settings()
    mode = settings.OPENROUTER_API_MODE
    if mode == "auto":
        outputs = get_model_output_modalities(payload.model)
        mode = "images" if outputs == ("image",) else "chat"
        if mode == "chat" and payload.modalities is None and "image" in outputs:
            payload = payload.model_copy(update={"modalities": [kind for kind in outputs if kind in ("text", "image")]})
    endpoint = "images" if mode == "images" else "chat/completions"
    body = create_image_payload(payload) if mode == "images" else payload.model_dump(exclude_none=True)
    api_key = settings.API_KEY.get_secret_value()
    try:
        response = requests.post(
            url=f"https://openrouter.ai/api/v1/{endpoint}",
            headers={"Authorization": f"Bearer {api_key}"},
            json=body,
            timeout=180,
        )
    except requests.Timeout as exc:
        log(f"OpenRouter /{endpoint} request timed out", level=logging.ERROR)
        raise HTTPException(status_code=504, detail="The model timed out. Please try again.") from exc
    except requests.RequestException as exc:
        log(f"OpenRouter /{endpoint} connection failed ({type(exc).__name__})", level=logging.ERROR)
        raise HTTPException(status_code=502, detail="Could not connect to OpenRouter. Check the server's network connection.") from exc

    try:
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError("Expected a JSON object")
        if not response.ok or result.get("error"):
            message = provider_error_message(result, payload, api_key)
            detail = f"OpenRouter returned HTTP {response.status_code}: {message}"
            log(f"OpenRouter /{endpoint} request failed: {detail}", level=logging.ERROR)
            raise HTTPException(status_code=502, detail=detail)
        return image_response_to_completion(result, payload.model) if mode == "images" else result
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        log(f"OpenRouter /{endpoint} returned an invalid response (HTTP {response.status_code})", level=logging.ERROR)
        raise HTTPException(status_code=502, detail=f"OpenRouter returned an invalid response (HTTP {response.status_code}).") from exc
