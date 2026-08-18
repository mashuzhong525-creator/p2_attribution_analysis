"""Pydantic 请求模型。"""

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class CreateConversationRequest(BaseModel):
    title: str = "新会话"


class UpdateConversationRequest(BaseModel):
    conversation_id: int
    title: str


class DeleteConversationRequest(BaseModel):
    conversation_ids: list[int]


class WsTokenRequest(BaseModel):
    conversation_id: int
