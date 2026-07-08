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


class OrderCreate(BaseModel):
    item_name: str = Field(min_length=1, max_length=120)
    shipping_address: str = Field(min_length=1, max_length=240)


class OrderResponse(BaseModel):
    id: int
    item_name: str
    shipping_address: str
    owner_id: int
    tenant_id: str


class OrderQueryRequest(BaseModel):
    order_id: int = Field(ge=1)


class AddressUpdateRequest(BaseModel):
    order_id: int = Field(ge=1)
    new_address: str = Field(min_length=1, max_length=240)
    confirmation_token: str | None = Field(default=None, min_length=8, max_length=128)


class AgentToolResponse(BaseModel):
    tool_name: str
    safe: bool
    message: str
    order: OrderResponse
    requires_confirmation: bool = False
    confirmation_token: str | None = None
    audit_log_id: int | None = None


class ToolAuditLogResponse(BaseModel):
    id: int
    actor_user_id: int
    actor_tenant_id: str
    tool_name: str
    safe: bool
    action: str
    target_order_id: int
    allowed: bool
    outcome: str
    reason: str
    created_at: str
