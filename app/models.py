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
