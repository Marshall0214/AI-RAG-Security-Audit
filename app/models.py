from dataclasses import dataclass
from enum import Enum


class Role(str, Enum):
    USER = "user"
    ADMIN = "admin"


@dataclass
class User:
    id: int
    username: str
    password_hash: str
    tenant_id: str
    role: Role


@dataclass
class Document:
    id: int
    title: str
    content: str
    owner_id: int
    tenant_id: str


@dataclass
class DocumentChunk:
    id: int
    document_id: int
    chunk_index: int
    text: str
    owner_id: int
    tenant_id: str


@dataclass
class Order:
    id: int
    item_name: str
    shipping_address: str
    owner_id: int
    tenant_id: str


@dataclass
class ToolAuditLog:
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


@dataclass
class PendingToolConfirmation:
    token: str
    actor_user_id: int
    actor_tenant_id: str
    tool_name: str
    target_order_id: int
    new_address: str
    consumed: bool
