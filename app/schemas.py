from pydantic import BaseModel, Field

from app.models import Role


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6, max_length=128)
    tenant_id: str = Field(min_length=2, max_length=64)
    role: Role = Role.USER


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    username: str
    tenant_id: str
    role: Role


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=20_000)


class DocumentResponse(BaseModel):
    id: int
    title: str
    content: str
    owner_id: int
    tenant_id: str


class RagQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    max_results: int = Field(default=5, ge=1, le=20)


class RagChunkMatch(BaseModel):
    chunk_id: int
    document_id: int
    document_title: str
    chunk_index: int
    text: str
    owner_id: int
    tenant_id: str
    score: int


class RagQueryResponse(BaseModel):
    query: str
    answer: str
    match_count: int
    matches: list[RagChunkMatch]
