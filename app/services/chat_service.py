import requests
import json

from typing import Any
from config import get_settings
from schemas.responses import *

config = get_settings()

def get_system_prompt() -> str | None:
    try:
        with open("system_prompt.txt", "r") as f:
            return f.read()
    except Exception as e:
        print(f"Error reading system prompt file: {e}")
        return None

def merge_request_variables(input: str, system_prompt: str | None, context: list[ChatCompletedReponse] | None) -> str:
    if system_prompt:
        input = system_prompt + "\n" + input
    if context:
        for message in context:
            role = ChatCompletedReponse.model_validate(message).choices[0].message.role
            content = ChatCompletedReponse.model_validate(message).choices[0].message.content
            if role and content:
                input += f"\n{role}: {content}"
    return input

def send_request_to_openrouter(content : str) -> dict[Any, Any] | None:
    settings = get_settings()

    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.API_KEY.get_secret_value()}",
        },
        data = json.dumps ({
            "model": f"{settings.MODEL}",
            "messages": [
                {
                "role": "user",
                "content" : f"{content}"
                }
            ]
        })

    )

    match response.status_code:
        case 200:
            return response.json()

        case _:
            print(response.status_code)
            return None
