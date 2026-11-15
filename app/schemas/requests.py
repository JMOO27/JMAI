from pydantic import BaseModel

class ChatMessage(BaseModel):
    role : str
    content : str

class RequestPayload(BaseModel):
    model : str
    messages : list[ChatMessage]