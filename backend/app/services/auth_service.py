from sqlalchemy.orm import Session
from app.models.auth import User, Workspace, WorkspaceMember
from app.schemas.auth import UserCreate
from app.core.security import get_password_hash

class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def create_user(self, payload: UserCreate) -> User:
        if self.db.query(User).filter_by(email=payload.email).first():
            raise ValueError("Email already registered")

        # Create user
        user = User(
            email=payload.email,
            hashed_password=get_password_hash(payload.password),
            full_name=payload.full_name
        )
        self.db.add(user)
        self.db.commit()

        # Create default workspace
        ws = Workspace(name=f"{payload.email.split('@')[0]}'s Workspace")
        self.db.add(ws)
        self.db.commit()

        # Create membership
        member = WorkspaceMember(
            workspace_id=ws.id,
            user_id=user.id,
            role="OWNER"
        )
        self.db.add(member)
        self.db.commit()

        return user

    def get_user_by_email(self, email: str) -> User:
        return self.db.query(User).filter_by(email=email).first()

    def get_user_default_workspace(self, user_id: str) -> Workspace:
        member = self.db.query(WorkspaceMember).filter_by(user_id=user_id).first()
        if member:
            return self.db.query(Workspace).filter_by(id=member.workspace_id).first()
        return None
