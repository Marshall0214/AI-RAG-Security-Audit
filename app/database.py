from datetime import datetime, timezone
from secrets import token_urlsafe

from app.models import (
    Document,
    DocumentChunk,
    Order,
    PendingToolConfirmation,
    Role,
    ToolAuditLog,
    User,
)
from app.rag import chunk_text, score_chunk
from app.security import hash_password


class InMemoryDatabase:
    def __init__(self) -> None:
        self.users: dict[int, User] = {}
        self.documents: dict[int, Document] = {}
        self.document_chunks: dict[int, DocumentChunk] = {}
        self.orders: dict[int, Order] = {}
        self.tool_audit_logs: dict[int, ToolAuditLog] = {}
        self.pending_tool_confirmations: dict[str, PendingToolConfirmation] = {}
        self._user_id = 1
        self._document_id = 1
        self._chunk_id = 1
        self._order_id = 1
        self._audit_log_id = 1

        self.create_user(
            username="admin",
            password="admin123",
            tenant_id="platform",
            role=Role.ADMIN,
        )

    def create_user(
        self,
        username: str,
        password: str,
        tenant_id: str,
        role: Role,
    ) -> User:
        if self.get_user_by_username(username) is not None:
            raise ValueError("username already exists")

        user = User(
            id=self._user_id,
            username=username,
            password_hash=hash_password(password),
            tenant_id=tenant_id,
            role=role,
        )
        self.users[user.id] = user
        self._user_id += 1
        return user

    def get_user_by_username(self, username: str) -> User | None:
        return next(
            (user for user in self.users.values() if user.username == username),
            None,
        )

    def get_user(self, user_id: int) -> User | None:
        return self.users.get(user_id)

    def create_document(self, title: str, content: str, owner: User) -> Document:
        document = Document(
            id=self._document_id,
            title=title,
            content=content,
            owner_id=owner.id,
            tenant_id=owner.tenant_id,
        )
        self.documents[document.id] = document
        self._document_id += 1
        self.create_chunks_for_document(document)
        return document

    def create_chunks_for_document(self, document: Document) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        for index, text in enumerate(chunk_text(document.content)):
            chunk = DocumentChunk(
                id=self._chunk_id,
                document_id=document.id,
                chunk_index=index,
                text=text,
                owner_id=document.owner_id,
                tenant_id=document.tenant_id,
            )
            self.document_chunks[chunk.id] = chunk
            self._chunk_id += 1
            chunks.append(chunk)

        return chunks

    def list_documents_for_user(self, user: User) -> list[Document]:
        if user.role == Role.ADMIN:
            return list(self.documents.values())

        return [
            document
            for document in self.documents.values()
            if document.owner_id == user.id and document.tenant_id == user.tenant_id
        ]

    def get_document_for_user(
        self,
        document_id: int,
        user: User,
    ) -> Document | None:
        document = self.documents.get(document_id)
        if document is None:
            return None

        if user.role == Role.ADMIN:
            return document

        if document.owner_id == user.id and document.tenant_id == user.tenant_id:
            return document

        return None

    def create_order(
        self,
        item_name: str,
        shipping_address: str,
        owner: User,
    ) -> Order:
        order = Order(
            id=self._order_id,
            item_name=item_name,
            shipping_address=shipping_address,
            owner_id=owner.id,
            tenant_id=owner.tenant_id,
        )
        self.orders[order.id] = order
        self._order_id += 1
        return order

    def list_orders_for_user(self, user: User) -> list[Order]:
        if user.role == Role.ADMIN:
            return list(self.orders.values())

        return [
            order
            for order in self.orders.values()
            if order.owner_id == user.id and order.tenant_id == user.tenant_id
        ]

    def get_order_for_user(self, order_id: int, user: User) -> Order | None:
        order = self.orders.get(order_id)
        if order is None:
            return None

        if user.role == Role.ADMIN:
            return order

        if order.owner_id == user.id and order.tenant_id == user.tenant_id:
            return order

        return None

    def get_order_without_authorization(self, order_id: int) -> Order | None:
        return self.orders.get(order_id)

    def update_order_address(self, order: Order, new_address: str) -> Order:
        order.shipping_address = new_address
        return order

    def create_tool_audit_log(
        self,
        actor: User,
        tool_name: str,
        safe: bool,
        action: str,
        target_order_id: int,
        allowed: bool,
        outcome: str,
        reason: str,
    ) -> ToolAuditLog:
        audit_log = ToolAuditLog(
            id=self._audit_log_id,
            actor_user_id=actor.id,
            actor_tenant_id=actor.tenant_id,
            tool_name=tool_name,
            safe=safe,
            action=action,
            target_order_id=target_order_id,
            allowed=allowed,
            outcome=outcome,
            reason=reason,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self.tool_audit_logs[audit_log.id] = audit_log
        self._audit_log_id += 1
        return audit_log

    def list_tool_audit_logs_for_user(self, user: User) -> list[ToolAuditLog]:
        if user.role == Role.ADMIN:
            return list(self.tool_audit_logs.values())

        return [
            audit_log
            for audit_log in self.tool_audit_logs.values()
            if audit_log.actor_user_id == user.id
            and audit_log.actor_tenant_id == user.tenant_id
        ]

    def create_pending_address_confirmation(
        self,
        actor: User,
        order: Order,
        new_address: str,
    ) -> PendingToolConfirmation:
        confirmation = PendingToolConfirmation(
            token=token_urlsafe(24),
            actor_user_id=actor.id,
            actor_tenant_id=actor.tenant_id,
            tool_name="address-update",
            target_order_id=order.id,
            new_address=new_address,
            consumed=False,
        )
        self.pending_tool_confirmations[confirmation.token] = confirmation
        return confirmation

    def consume_address_confirmation(
        self,
        token: str,
        actor: User,
        order_id: int,
        new_address: str,
    ) -> bool:
        confirmation = self.pending_tool_confirmations.get(token)
        if confirmation is None or confirmation.consumed:
            return False

        if confirmation.actor_user_id != actor.id:
            return False

        if confirmation.actor_tenant_id != actor.tenant_id:
            return False

        if confirmation.target_order_id != order_id:
            return False

        if confirmation.new_address != new_address:
            return False

        confirmation.consumed = True
        return True

    def search_chunks_for_user(
        self,
        query: str,
        user: User,
        max_results: int,
    ) -> list[tuple[DocumentChunk, int]]:
        if user.role == Role.ADMIN:
            chunks = list(self.document_chunks.values())
        else:
            chunks = [
                chunk
                for chunk in self.document_chunks.values()
                if chunk.owner_id == user.id and chunk.tenant_id == user.tenant_id
            ]

        return self._rank_chunks(query, chunks, max_results)

    def search_all_chunks(
        self,
        query: str,
        max_results: int,
    ) -> list[tuple[DocumentChunk, int]]:
        return self._rank_chunks(query, list(self.document_chunks.values()), max_results)

    def _rank_chunks(
        self,
        query: str,
        chunks: list[DocumentChunk],
        max_results: int,
    ) -> list[tuple[DocumentChunk, int]]:
        scored_chunks: list[tuple[DocumentChunk, int]] = []
        for chunk in chunks:
            document = self.documents.get(chunk.document_id)
            if document is None:
                continue

            score = score_chunk(query, chunk, document.title)
            if score > 0:
                scored_chunks.append((chunk, score))

        scored_chunks.sort(key=lambda item: item[1], reverse=True)
        return scored_chunks[:max_results]


db = InMemoryDatabase()
