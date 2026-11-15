from pydantic import BaseModel
from typing import Literal


class ImageURL(BaseModel):
    url: str


class TextPart(BaseModel):
    type: Literal["text"]
    text: str


class ImagePart(BaseModel):
    type: Literal["image_url"]
    image_url: ImageURL

class ChatMessage(BaseModel):
    role : str
    content: str | list[TextPart | ImagePart] | None
    images: list[ImagePart] | None = None

class RequestPayload(BaseModel):
    model : str
    messages : list[ChatMessage]
    modalities: list[Literal["text", "image"]] | None = None
