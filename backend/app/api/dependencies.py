from fastapi import Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.project_service import ProjectService
from app.services.scrape_service import ScrapeService
from app.services.analytics_service import AnalyticsService
from app.services.analysis_service import AnalysisService
from app.services.discovery_service import DiscoveryService
from app.providers.ai.factory import get_ai_provider
from app.providers.embedding.factory import get_embedding_provider
from app.services.generation_service import GenerationService
from fastapi import HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from app.core.security import settings
from app.models.auth import User, Workspace, WorkspaceMember

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter_by(id=user_id).first()
    if user is None:
        raise credentials_exception
    return user

def get_current_workspace(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Workspace:
    # Basic setup: get the first workspace the user is in.
    member = db.query(WorkspaceMember).filter_by(user_id=user.id).first()
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of any workspace")
    ws = db.query(Workspace).filter_by(id=member.workspace_id).first()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws

def get_project_service(db: Session = Depends(get_db), ws: Workspace = Depends(get_current_workspace)) -> ProjectService:
    return ProjectService(db, ws)

def get_scrape_service(db: Session = Depends(get_db), ws: Workspace = Depends(get_current_workspace)) -> ScrapeService:
    return ScrapeService(db, ws)

def get_analytics_service(db: Session = Depends(get_db), ws: Workspace = Depends(get_current_workspace)) -> AnalyticsService:
    return AnalyticsService(db, ws)

def get_analysis_service(db: Session = Depends(get_db), ws: Workspace = Depends(get_current_workspace)) -> AnalysisService:
    return AnalysisService(db, get_ai_provider(), get_embedding_provider(), ws)

def get_discovery_service(db: Session = Depends(get_db), ws: Workspace = Depends(get_current_workspace)) -> DiscoveryService:
    return DiscoveryService(db, ws)

def get_generation_service(db: Session = Depends(get_db), ws: Workspace = Depends(get_current_workspace)) -> GenerationService:
    return GenerationService(db, get_ai_provider(), get_embedding_provider(), None, ws)

from app.services.post_service import PostService

def get_post_service(db: Session = Depends(get_db), ws: Workspace = Depends(get_current_workspace)) -> PostService:
    return PostService(db, ws)
