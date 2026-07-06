from app.models import Document, Role, User
from app.security import hash_password


class InMemoryDatabase:
    def __init__(self) -> None:
        self.users: dict[int, User] = {}
        self.documents: dict[int, Document] = {}
        self._user_id = 1
        self._document_id = 1

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
        return document

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


db = InMemoryDatabase()
