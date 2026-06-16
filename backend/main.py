from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
import uuid
import database, models, schemas, auth_utils
from database import engine, get_db

# Automatically create tables on startup
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="VoiceMind AI API", version="1.0.0")

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Authentication Dependency to secure routes
def get_current_user(token: str = Depends(lambda x: None), db: Session = Depends(get_db)):
    # Simple bearer token parser
    # We retrieve token from Header
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    from fastapi import Request
    
    # Custom authorization extraction
    async def get_token_from_header(request: Request) -> str:
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing Authorization Header",
            )
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token header format",
            )
        return parts[1]
    
    return get_token_from_header

async def get_active_user(request: Request, db: Session = Depends(get_db)) -> models.User:
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization Header",
        )
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization token",
        )
    token = parts[1]
    payload = auth_utils.decode_token(token)
    user_id = payload.get("sub")
    token_type = payload.get("type")
    
    if not user_id or token_type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
        )
        
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive or not found",
        )
    return user

# --- AUTH ENDPOINTS ---

@app.post("/auth/register", response_model=schemas.TokenResponse)
def register(user_in: schemas.UserRegister, db: Session = Depends(get_db)):
    # Check if user already exists
    existing_user = db.query(models.User).filter(models.User.email == user_in.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create new user
    hashed_pwd = auth_utils.get_password_hash(user_in.password)
    new_user = models.User(
        email=user_in.email,
        hashed_password=hashed_pwd,
        display_name=user_in.display_name or user_in.email.split("@")[0],
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Generate JWT pair
    access_token = auth_utils.create_access_token(data={"sub": new_user.id})
    refresh_token_jwt = auth_utils.create_refresh_token(data={"sub": new_user.id})

    # Store refresh token
    expires_at = datetime.utcnow() + timedelta(days=auth_utils.REFRESH_TOKEN_EXPIRE_DAYS)
    db_refresh_token = models.RefreshToken(
        token=refresh_token_jwt,
        user_id=new_user.id,
        expires_at=expires_at,
    )
    db.add(db_refresh_token)
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token_jwt,
        "user": new_user,
    }

@app.post("/auth/login", response_model=schemas.TokenResponse)
def login(credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == credentials.email).first()
    if not user or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email or password",
        )

    if not auth_utils.verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email or password",
        )

    # Generate JWT pair
    access_token = auth_utils.create_access_token(data={"sub": user.id})
    refresh_token_jwt = auth_utils.create_refresh_token(data={"sub": user.id})

    # Store refresh token
    expires_at = datetime.utcnow() + timedelta(days=auth_utils.REFRESH_TOKEN_EXPIRE_DAYS)
    db_refresh_token = models.RefreshToken(
        token=refresh_token_jwt,
        user_id=user.id,
        expires_at=expires_at,
    )
    db.add(db_refresh_token)
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token_jwt,
        "user": user,
    }

@app.post("/auth/refresh", response_model=schemas.TokenResponse)
def refresh_token(refresh_in: schemas.TokenRefreshRequest, db: Session = Depends(get_db)):
    payload = auth_utils.decode_token(refresh_in.refresh_token)
    user_id = payload.get("sub")
    token_type = payload.get("type")

    if not user_id or token_type != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Check database for active token
    db_token = db.query(models.RefreshToken).filter(
        models.RefreshToken.token == refresh_in.refresh_token,
        models.RefreshToken.revoked == False,
        models.RefreshToken.expires_at > datetime.utcnow()
    ).first()

    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is expired or revoked",
        )

    # Revoke old token
    db_token.revoked = True
    db.commit()

    # Get user
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Create new pair
    new_access = auth_utils.create_access_token(data={"sub": user.id})
    new_refresh = auth_utils.create_refresh_token(data={"sub": user.id})

    # Store new refresh token
    expires_at = datetime.utcnow() + timedelta(days=auth_utils.REFRESH_TOKEN_EXPIRE_DAYS)
    new_db_token = models.RefreshToken(
        token=new_refresh,
        user_id=user.id,
        expires_at=expires_at,
    )
    db.add(new_db_token)
    db.commit()

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "user": user,
    }

@app.post("/auth/oauth/google", response_model=schemas.TokenResponse)
def oauth_google(oauth_in: schemas.OAuthRequest, db: Session = Depends(get_db)):
    # Standard Google Login verification:
    # Under real circumstances, verify id_token with google library.
    # For this system, we decode or read mock token (e.g. mock-google-token-email@example.com).
    email = "google-user@example.com"
    google_id = "g-123456"
    display_name = oauth_in.display_name or "Google User"

    if oauth_in.token.startswith("mock-google-"):
        email = oauth_in.token.replace("mock-google-", "")
        google_id = f"g-{hash(email)}"
        display_name = email.split("@")[0].capitalize()

    # Check if user exists by google_id or email
    user = db.query(models.User).filter(
        (models.User.google_id == google_id) | (models.User.email == email)
    ).first()

    if not user:
        # Register new OAuth user
        user = models.User(
            email=email,
            google_id=google_id,
            display_name=display_name,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif not user.google_id:
        # Link Google ID to existing email account
        user.google_id = google_id
        db.commit()

    # Generate JWT pair
    access_token = auth_utils.create_access_token(data={"sub": user.id})
    refresh_token_jwt = auth_utils.create_refresh_token(data={"sub": user.id})

    # Store refresh token
    expires_at = datetime.utcnow() + timedelta(days=auth_utils.REFRESH_TOKEN_EXPIRE_DAYS)
    db_refresh_token = models.RefreshToken(
        token=refresh_token_jwt,
        user_id=user.id,
        expires_at=expires_at,
    )
    db.add(db_refresh_token)
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token_jwt,
        "user": user,
    }

@app.post("/auth/oauth/apple", response_model=schemas.TokenResponse)
def oauth_apple(oauth_in: schemas.OAuthRequest, db: Session = Depends(get_db)):
    email = "apple-user@example.com"
    apple_id = "a-123456"
    display_name = oauth_in.display_name or "Apple User"

    if oauth_in.token.startswith("mock-apple-"):
        email = oauth_in.token.replace("mock-apple-", "")
        apple_id = f"a-{hash(email)}"
        display_name = email.split("@")[0].capitalize()

    user = db.query(models.User).filter(
        (models.User.apple_id == apple_id) | (models.User.email == email)
    ).first()

    if not user:
        user = models.User(
            email=email,
            apple_id=apple_id,
            display_name=display_name,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif not user.apple_id:
        user.apple_id = apple_id
        db.commit()

    access_token = auth_utils.create_access_token(data={"sub": user.id})
    refresh_token_jwt = auth_utils.create_refresh_token(data={"sub": user.id})

    expires_at = datetime.utcnow() + timedelta(days=auth_utils.REFRESH_TOKEN_EXPIRE_DAYS)
    db_refresh_token = models.RefreshToken(
        token=refresh_token_jwt,
        user_id=user.id,
        expires_at=expires_at,
    )
    db.add(db_refresh_token)
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token_jwt,
        "user": user,
    }

@app.post("/auth/password-reset/request")
def request_password_reset(reset_in: schemas.PasswordResetRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == reset_in.email).first()
    if not user:
        # Return success even if email is not found to prevent user enumeration attacks
        return {"message": "Password reset token sent if email exists."}
    
    # Generate mock reset token (usually sent via email)
    reset_token = f"reset-{user.id}-{int(datetime.utcnow().timestamp())}"
    return {
        "message": "Password reset token sent if email exists.",
        "reset_token": reset_token # Returned for UI testing in development
    }

@app.post("/auth/password-reset/confirm")
def confirm_password_reset(confirm_in: schemas.PasswordResetConfirm, db: Session = Depends(get_db)):
    # Validate token prefix
    if not confirm_in.token.startswith("reset-"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )
    
    user_id = confirm_in.token.split("-")[1]
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset token",
        )

    # Reset password
    user.hashed_password = auth_utils.get_password_hash(confirm_in.new_password)
    db.commit()
    return {"message": "Password reset successfully"}

@app.post("/auth/logout")
def logout(refresh_in: schemas.TokenRefreshRequest, db: Session = Depends(get_db)):
    db_token = db.query(models.RefreshToken).filter(
        models.RefreshToken.token == refresh_in.refresh_token
    ).first()
    if db_token:
        db_token.revoked = True
        db.commit()
    return {"message": "Logged out successfully"}

# --- PROTECTED APP ENDPOINTS ---

class VoiceNoteResponse(BaseModel):
    id: str
    title: str
    createdAt: str
    durationSec: float
    filePath: str
    status: str
    transcription: Optional[str] = None
    summary: Optional[str] = None
    tags: List[str] = []

@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.get("/notes", response_model=List[VoiceNoteResponse])
def get_notes(current_user: models.User = Depends(get_active_user)):
    # Secured with user token validation dependency!
    return [
        {
            "id": "1",
            "title": f"Note for {current_user.display_name}",
            "createdAt": datetime.utcnow().isoformat() + "Z",
            "durationSec": 45.2,
            "filePath": "/audio/note_1.m4a",
            "status": "completed",
            "transcription": "This is a secured voice note for your account.",
            "summary": "Secured note catalog.",
            "tags": ["private", "authenticated"]
        }
    ]

@app.post("/notes/upload", response_model=VoiceNoteResponse)
async def upload_audio(file: UploadFile = File(...), current_user: models.User = Depends(get_active_user)):
    note_id = str(uuid.uuid4())
    return {
        "id": note_id,
        "title": f"Note ({file.filename})",
        "createdAt": datetime.utcnow().isoformat() + "Z",
        "durationSec": 15.0,
        "filePath": f"/audio/{current_user.id}_{note_id}_{file.filename}",
        "status": "completed",
        "transcription": "Authenticated voice note audio file successfully uploaded.",
        "summary": "Audio Upload.",
        "tags": ["uploaded"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
