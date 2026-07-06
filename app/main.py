from fastapi import Depends, FastAPI, HTTPException, status

from app.auth import get_current_user, require_admin
from app.database import db
from app.models import DocumentChunk, User
from app.schemas import (
    DocumentCreate,
    DocumentResponse,
    LoginRequest,
    RagChunkMatch,
    RagQueryRequest,
    RagQueryResponse,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.security import create_token, verify_password

app = FastAPI(
    title="AI-RAG-Security-Audit",
    description="AI application security audit lab for RAG and Agent scenarios.",
    version="0.2.0",
)


def to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        tenant_id=user.tenant_id,
        role=user.role,
    )


def to_rag_response(
    query: str,
    matches: list[tuple[DocumentChunk, int]],
    vulnerable: bool,
) -> RagQueryResponse:
    chunk_matches: list[RagChunkMatch] = []
    for chunk, score in matches:
        document = db.documents[chunk.document_id]
        chunk_matches.append(
            RagChunkMatch(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                document_title=document.title,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                owner_id=chunk.owner_id,
                tenant_id=chunk.tenant_id,
                score=score,
            )
        )

    if not chunk_matches:
        answer = "No relevant authorized document chunks were found."
    elif vulnerable:
        answer = (
            "VULNERABLE DEMO: results were retrieved without user or tenant "
            "filtering. This may expose another user's document content."
        )
    else:
        answer = (
            "Retrieved relevant chunks after applying current-user access control. "
            "Only authorized document chunks are included."
        )

    return RagQueryResponse(
        query=query,
        answer=answer,
        match_count=len(chunk_matches),
        matches=chunk_matches,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/register", response_model=UserResponse, status_code=201)
def register(request: RegisterRequest) -> UserResponse:
    try:
        user = db.create_user(
            username=request.username,
            password=request.password,
            tenant_id=request.tenant_id,
            role=request.role,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    return to_user_response(user)


@app.post("/auth/login", response_model=TokenResponse)
def login(request: LoginRequest) -> TokenResponse:
    user = db.get_user_by_username(request.username)
    if user is None or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid username or password",
        )

    token = create_token({"sub": user.id, "role": user.role.value})
    return TokenResponse(access_token=token)


@app.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return to_user_response(current_user)


@app.post("/documents", response_model=DocumentResponse, status_code=201)
def create_document(
    request: DocumentCreate,
    current_user: User = Depends(get_current_user),
) -> DocumentResponse:
    document = db.create_document(
        title=request.title,
        content=request.content,
        owner=current_user,
    )
    return DocumentResponse(**document.__dict__)


@app.get("/documents", response_model=list[DocumentResponse])
def list_documents(
    current_user: User = Depends(get_current_user),
) -> list[DocumentResponse]:
    documents = db.list_documents_for_user(current_user)
    return [DocumentResponse(**document.__dict__) for document in documents]


@app.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
) -> DocumentResponse:
    document = db.get_document_for_user(document_id, current_user)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="document not found or access denied",
        )
    return DocumentResponse(**document.__dict__)


@app.get("/admin/documents", response_model=list[DocumentResponse])
def admin_list_documents(
    _: User = Depends(require_admin),
) -> list[DocumentResponse]:
    return [
        DocumentResponse(**document.__dict__)
        for document in db.documents.values()
    ]


@app.post("/rag/query", response_model=RagQueryResponse)
def safe_rag_query(
    request: RagQueryRequest,
    current_user: User = Depends(get_current_user),
) -> RagQueryResponse:
    matches = db.search_chunks_for_user(
        query=request.query,
        user=current_user,
        max_results=request.max_results,
    )
    return to_rag_response(request.query, matches, vulnerable=False)


@app.post("/lab/vulnerable-rag/query", response_model=RagQueryResponse)
def vulnerable_rag_query(
    request: RagQueryRequest,
    _: User = Depends(get_current_user),
) -> RagQueryResponse:
    matches = db.search_all_chunks(
        query=request.query,
        max_results=request.max_results,
    )
    return to_rag_response(request.query, matches, vulnerable=True)
