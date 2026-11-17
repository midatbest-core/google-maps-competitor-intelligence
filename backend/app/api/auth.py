from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.dependencies import get_db, get_current_user, get_current_workspace
from app.services.auth_service import AuthService
from app.schemas.auth import UserCreate, UserLogin, Token, UserResponse, DemoStatusResponse
from app.core.security import verify_password, create_access_token
from app.core.config import settings
from app.models.auth import User, Workspace, WorkspaceMember

auth_router = APIRouter(tags=["auth"], prefix="/auth")

def get_auth_service(db: Session = Depends(get_db)):
    return AuthService(db)

@auth_router.get("/demo-status", response_model=DemoStatusResponse)
def get_demo_status():
    is_enabled = bool(
        settings.ENABLE_DEMO_LOGIN
        and settings.DEMO_ADMIN_PASSWORD
        and settings.DEMO_ADMIN_PASSWORD.strip()
    )
    return DemoStatusResponse(
        enabled=is_enabled,
        email=settings.DEMO_ADMIN_EMAIL if is_enabled else None
    )

@auth_router.post("/demo-login", response_model=Token)
def demo_login(service: AuthService = Depends(get_auth_service)):
    if not settings.ENABLE_DEMO_LOGIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo login is disabled in this environment."
        )

    if not settings.DEMO_ADMIN_PASSWORD or not settings.DEMO_ADMIN_PASSWORD.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Demo login is not configured: admin credentials missing."
        )

    user = service.get_user_by_email(settings.DEMO_ADMIN_EMAIL)
    if not user:
        user = service.create_user(UserCreate(
            email=settings.DEMO_ADMIN_EMAIL,
            password=settings.DEMO_ADMIN_PASSWORD,
            full_name=settings.DEMO_ADMIN_NAME
        ))

    ws = service.get_user_default_workspace(user.id)
    if not ws:
        ws = Workspace(name="Demo Workspace")
        service.db.add(ws)
        service.db.flush()
        member = WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="OWNER")
        service.db.add(member)
        service.db.commit()

    access_token = create_access_token(subject=user.id)
    return {"access_token": access_token, "token_type": "bearer"}

@auth_router.post("/register", response_model=UserResponse)
def register(payload: UserCreate, service: AuthService = Depends(get_auth_service)):
    try:
        user = service.create_user(payload)
        ws = service.get_user_default_workspace(user.id)
        resp = UserResponse.model_validate(user)
        if ws:
            resp.workspace_id = ws.id
        return resp
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@auth_router.post("/login", response_model=Token)
def login(payload: UserLogin, service: AuthService = Depends(get_auth_service)):
    user = service.get_user_by_email(payload.email)
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    access_token = create_access_token(subject=user.id)
    return {"access_token": access_token, "token_type": "bearer"}

@auth_router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user), ws: Workspace = Depends(get_current_workspace)):
    resp = UserResponse.model_validate(user)
    if ws:
        resp.workspace_id = ws.id
    return resp

@auth_router.post("/logout")
def logout():
    # Since we use stateless JWT, logout is primarily a client-side action (deleting token).
    return {"message": "Logged out successfully"}
