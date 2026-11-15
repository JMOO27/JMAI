import logging
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from services.chat_service import create_request_payload, get_system_prompt, send_request_to_openrouter
from services.chat_storage_service import create_db, get_unique_conv_id, create_conv, create_chat, get_conv, list_conversations
from schemas.requests import ChatMessage
from schemas.responses import ChatCompletedReponse
from app_logging import log
from config import get_settings

def create_app() -> FastAPI:
    app = FastAPI()
    settings = get_settings()
    create_db()

    @app.post("/api/create_conversation")
    def create_conversation():
        conv_id = get_unique_conv_id()
        create_conv(conv_id)
        system_prompt = get_system_prompt()
        if system_prompt is not None:
            create_chat(conv_id, system_prompt)
        return {"conv_id": conv_id}

    @app.get("/api/conversations")
    def conversations():
        return list_conversations()

    @app.post("/api/send_chat")
    def send_chat(input: ChatMessage, conv_id: int):
        if input.role != "user":
            raise HTTPException(status_code=422, detail="Only user messages can be sent.")
        if not input.content:
            raise HTTPException(status_code=422, detail="A message or image is required.")
        try:
            get_conv(conv_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="Conversation not found.") from exc

        # save only successful turns so a retry does not duplicate the user's message.
        payload = create_request_payload(input, conv_id)
        try:
            response = ChatCompletedReponse.model_validate(send_request_to_openrouter(payload))
            if not response.choices:
                raise HTTPException(status_code=502, detail="The model returned no reply.")
        except ValidationError as exc:
            log("Invalid model response", level=logging.ERROR)
            raise HTTPException(status_code=502, detail="The model returned an invalid response.") from exc

        create_chat(conv_id, input)
        create_chat(conv_id, ChatMessage.model_validate(response.choices[0].message.model_dump()))
        return response

    @app.get("/api/get_conversation")
    def get_conversation(conv_id: int) -> list[ChatCompletedReponse | ChatMessage]:
        try:
            return get_conv(conv_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="Conversation not found.") from exc

    # Vite output is served on the same origin as the existing API.
    frontend_dir = Path(settings.FRONTEND_DIR)
    if (frontend_dir / "dist" / "index.html").is_file():
        frontend_dir = frontend_dir / "dist"
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
    return app


def main():
    log("Starting server...")
    uvicorn.run(create_app(), port=8000)


if __name__ == "__main__":
    main()
