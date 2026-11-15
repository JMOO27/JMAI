import logging
import json
from pydantic import ValidationError
import uvicorn

from services.chat_service import create_request_payload, get_system_prompt, send_request_to_openrouter, filter_completed_response_messages
from services.chat_storage_service import create_db, get_unique_conv_id, create_conv, create_chat, get_conv
from schemas.requests import ChatMessage
from schemas.responses import ChatCompletedReponse
from app_logging import log
from config import get_settings

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi import HTTPException

def main():
    app = FastAPI()
    log("Starting JMAI server...")
    settings = get_settings()

    @app.post("/api/create_conversation")
    async def create_conversation():
        # create a new converstation and return the conv_id
        # when a new conversation is created, the system prompt will be added to the conversation history as the first message
        create_db()
        conv_id = get_unique_conv_id()
        create_conv(conv_id)

        system_prompt : ChatMessage | None = get_system_prompt()

        if system_prompt is not None:
            create_chat(conv_id, system_prompt)
        return {"conv_id": conv_id}

    @app.post("/api/send_chat")
    async def send_chat(input : ChatMessage, conv_id : int):
        # send and recieve response from OpenRouter API

        # check if inside valid conv
        try:
            create_db()
            get_conv(conv_id)
        except Exception as e:
            log(f"Error occurred while checking conversation: {e}", level=logging.ERROR)
            raise HTTPException(
                status_code=404,
                detail=f"Conversation not found for conv_id {conv_id}."
            )
    
        create_chat(conv_id, input)

        req = create_request_payload(input, conv_id)
        try:
            response = ChatCompletedReponse.model_validate(send_request_to_openrouter(req))
        except ValidationError as e:
            log(f"Error occurred while validating OpenRouter response: {e}", level=logging.ERROR)
            raise HTTPException(
                status_code=500,
                detail=f"Something went wrong while processing the request, {e}."
            )

        create_chat(conv_id, ChatMessage(role=response.choices[0].message.role, content=response.choices[0].message.content))
        return response

    @app.get("/api/get_conversation")
    async def get_conversation(conv_id: int) -> list[ChatCompletedReponse | ChatMessage]:
        log(f"Retrieving chat history for conv_id {conv_id}...", level=logging.INFO)
        try:
            create_db()
            chat_history: list[ChatCompletedReponse | ChatMessage] = get_conv(conv_id)

            if len(chat_history) == 0:
                log(f"No chat history found for conv_id {conv_id}.", level=logging.WARNING)
                raise HTTPException(
                    status_code=404,
                    detail=f"No chat history found for conv_id {conv_id}."
                )   
            
            log(f"Successfully retrieved chat history for conv_id {conv_id}.", level=logging.INFO)
            return chat_history

        except Exception as e:
            if isinstance(e, HTTPException) and e.status_code == 404:
                log(f"Chat history was not found for conv_id {conv_id}: {e}", level=logging.ERROR)
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Something went wrong while retrieving chat history, {e}."
                )
        
    app.mount("/", StaticFiles(directory=settings.FRONTEND_DIR, html=True), name="frontend")
    uvicorn.run(app, port=8000)

if __name__ == "__main__":
    main()
