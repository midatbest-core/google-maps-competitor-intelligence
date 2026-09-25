from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from .base import BaseRepository
from app.models.post import Post

class PostRepository(BaseRepository[Post]):
    def __init__(self, session: Session):
        super().__init__(Post, session)

    def get_by_fingerprint(self, fingerprint: str) -> Optional[Post]:
        stmt = select(Post).where(Post.fingerprint == fingerprint)
        return self.session.scalar(stmt)
