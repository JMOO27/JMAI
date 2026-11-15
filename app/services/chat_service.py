import requests
import logging

from schemas.responses import ChatCompletedReponse
from schemas.requests import RequestPayload, ChatMessage
from services.chat_storage_service import get_conv
from app_logging import log
from config import get_settings

from typing import Any
from fastapi import HTTPException
from pydantic.v1 import ValidationError

config = get_settings()

def get_system_prompt() -> ChatMessage | None:
    try:
        with open("system_prompt.txt", "r") as f:
            system_prompt = {"role": "system", "content": f.read().strip()}
            ChatMessage.model_validate(system_prompt)
            return ChatMessage.model_validate(system_prompt)
    except Exception as e:
        if isinstance(e, ValidationError):
            log(f"System prompt is invalid: {e}", level=logging.ERROR)
        else:
            log(f"Error reading system prompt file: {e}", level=logging.ERROR)
    
    return None

def filter_completed_response_messages(input : list[ChatCompletedReponse]) -> list[ChatMessage]:
    # return a list of messages from the completed response objects
    # used to build expected chat history for OpenRouter request
    messages : list[ChatMessage] = []
    for item in input:
        try:
            completed_response = ChatCompletedReponse.model_validate(item)

            message= {"role": completed_response.choices[0].message.role, "content": completed_response.choices[0].message.content}
            validated_message = ChatMessage.model_validate(message)

            messages.append(validated_message)

        except Exception as e:
            if isinstance(e, ValidationError):
                log(f"Completed response message is invalid: {e}", level=logging.ERROR)
            log(f"Error occurred while filtering completed response messages: {e}", level=logging.ERROR)
    return messages

def create_request_payload(input: ChatMessage, conv_id: int) -> RequestPayload:
    # build the request payload for OpenRouter API
    payload = None
    context : list[ChatMessage] = []
    # get the conversation history
    past_messages = filter_completed_response_messages(get_conv(conv_id))

    # create the context
    for message in past_messages:
        context.append(message)

    # add the latest message to the context
    context.append(input)

    payload = RequestPayload(
        model = config.MODEL,
        messages = context
    )

    try:
        RequestPayload.model_validate(payload)

    except Exception as e:
        if isinstance(e, ValidationError):
            log(f"Request payload is invalid: {e}", level=logging.ERROR)
        else:
            log(f"Error occurred while validating request payload: {e}", level=logging.ERROR)
            log(f"Error occurred while validating response: {e}", level=logging.ERROR)
            raise HTTPException(
                status_code=500,
                detail=f"Invalid response from OpenRouter API."
            )

    return payload

def send_request_to_openrouter(payload : RequestPayload) -> dict[Any, Any] | None:
    settings = get_settings()

    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.API_KEY.get_secret_value()}",
        },
        data = payload.model_dump_json()
    )

    match response.status_code:
        case 200:
            return response.json()

        case _:
            print(response.status_code)
            return None
