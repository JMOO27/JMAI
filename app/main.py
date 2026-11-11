import logging

import uvicorn
import json

from services.chat_service import send_request_to_openrouter
from schemas import *
from config import get_settings
from schemas.responses import *
from services.chat_storage_service import *

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi import HTTPException

from pydantic import ValidationError

from services.chat_service import get_system_prompt
from services.chat_service import merge_request_variables

from app_logging import log

def main():
    app = FastAPI()
    log("Starting JMAI server...")
    settings = get_settings()
    
    @app.post("/api/create_chat")
    async def send_request(input : str, conv_id : int | None = None):
        system_prompt : str | None = get_system_prompt()

        if system_prompt is None:
            log("System prompt file is missing or unreadable.", level=logging.ERROR)
            raise HTTPException(
                status_code=500,
                detail="System prompt file is missing or unreadable."
            )
        
        context = get_conv(conv_id) if conv_id is not None else None
        input = merge_request_variables(input, system_prompt, context)
        req = send_request_to_openrouter(input)
        
        req_schema = None

        try:
            req_schema = ChatCompletedReponse.model_validate(req)

        except ValidationError as e:
            log(f"API response is not valid! {e}", level=logging.ERROR)
            raise HTTPException(
                status_code=500,
                detail=f"Something went wrong while sending request, {e}."
            )

        if conv_id is None:
            try:
                create_db()
                conv_id = get_unique_conv_id()
                create_conv(conv_id)
                create_chat(conv_id, json.dumps(req))
                return req_schema.choices[0].message.content
                
            except Exception as e:
                log(f"Error occurred while creating new chat: {e}", level=logging.ERROR)

        else:
            try:
                create_db()
                get_conv(conv_id)
                create_chat(conv_id, json.dumps(req))
                return req_schema.choices[0].message.content
            except Exception as e:
                log(f"Error occurred while creating chat: {e}", level=logging.ERROR)

    app.mount("/", StaticFiles(directory=settings.FRONTEND_DIR, html=True), name="frontend")

    uvicorn.run(app, port=8000)


if __name__ == "__main__":
    main()