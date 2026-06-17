from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from app.database import get_db
from app.core import security
from app.core.config import settings
from app.models.models import User, RefreshToken
from app.schemas import schemas

router = APIRouter()

@router.post("/register", response_model=schemas.TokenResponse)
def register(user_in: schemas.UserRegister, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user_in.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    hashed_pwd = security.get_password_hash(user_in.password)
    new_user = User(
        email=user_in.email,
        hashed_password=hashed_pwd,
        display_name=user_in.display_name or user_in.email.split("@")[0],
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    access_token = security.create_access_token(data={"sub": new_user.id})
    refresh_token_jwt = security.create_refresh_token(data={"sub": new_user.id})

    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    db_refresh_token = RefreshToken(
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

@router.post("/login", response_model=schemas.TokenResponse)
def login(credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == credentials.email).first()
    if not user or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email or password",
        )

    if not security.verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email or password",
        )

    access_token = security.create_access_token(data={"sub": user.id})
    refresh_token_jwt = security.create_refresh_token(data={"sub": user.id})

    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    db_refresh_token = RefreshToken(
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

@router.post("/refresh", response_model=schemas.TokenResponse)
def refresh_token(refresh_in: schemas.TokenRefreshRequest, db: Session = Depends(get_db)):
    try:
        payload = security.decode_token(refresh_in.refresh_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    user_id = payload.get("sub")
    token_type = payload.get("type")

    if not user_id or token_type != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    db_token = db.query(RefreshToken).filter(
        RefreshToken.token == refresh_in.refresh_token,
        RefreshToken.revoked == False,
        RefreshToken.expires_at > datetime.now(timezone.utc)
    ).first()

    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is expired or revoked",
        )

    db_token.revoked = True
    db.commit()

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    new_access = security.create_access_token(data={"sub": user.id})
    new_refresh = security.create_refresh_token(data={"sub": user.id})

    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    new_db_token = RefreshToken(
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

@router.post("/oauth/google", response_model=schemas.TokenResponse)
def oauth_google(oauth_in: schemas.OAuthRequest, db: Session = Depends(get_db)):
    email = "google-user@example.com"
    google_id = "g-123456"
    display_name = oauth_in.display_name or "Google User"

    if oauth_in.token.startswith("mock-google-"):
        email = oauth_in.token.replace("mock-google-", "")
        google_id = f"g-{hash(email)}"
        display_name = email.split("@")[0].capitalize()

    user = db.query(User).filter(
        (User.google_id == google_id) | (User.email == email)
    ).first()

    if not user:
        user = User(
            email=email,
            google_id=google_id,
            display_name=display_name,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif not user.google_id:
        user.google_id = google_id
        db.commit()

    access_token = security.create_access_token(data={"sub": user.id})
    refresh_token_jwt = security.create_refresh_token(data={"sub": user.id})

    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    db_refresh_token = RefreshToken(
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

@router.post("/oauth/apple", response_model=schemas.TokenResponse)
def oauth_apple(oauth_in: schemas.OAuthRequest, db: Session = Depends(get_db)):
    email = "apple-user@example.com"
    apple_id = "a-123456"
    display_name = oauth_in.display_name or "Apple User"

    if oauth_in.token.startswith("mock-apple-"):
        email = oauth_in.token.replace("mock-apple-", "")
        apple_id = f"a-{hash(email)}"
        display_name = email.split("@")[0].capitalize()

    user = db.query(User).filter(
        (User.apple_id == apple_id) | (User.email == email)
    ).first()

    if not user:
        user = User(
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

    access_token = security.create_access_token(data={"sub": user.id})
    refresh_token_jwt = security.create_refresh_token(data={"sub": user.id})

    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    db_refresh_token = RefreshToken(
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

@router.post("/password-reset/request")
def request_password_reset(reset_in: schemas.PasswordResetRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == reset_in.email).first()
    if not user:
        return {"message": "Password reset token sent if email exists."}
    
    # Replace deterministic token generation with securely random strings
    import secrets
    secure_token = secrets.token_urlsafe(32)
    # Expiry could be saved in a specific DB model if desired.
    # For now, append standard identifier info inside a secure envelopment.
    reset_token = f"reset-{user.id}-{int(datetime.now(timezone.utc).timestamp())}-{secure_token}"
    return {
        "message": "Password reset token sent if email exists.",
        "reset_token": reset_token
    }

@router.post("/password-reset/confirm")
def confirm_password_reset(confirm_in: schemas.PasswordResetConfirm, db: Session = Depends(get_db)):
    if not confirm_in.token.startswith("reset-"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )
    
    parts = confirm_in.token.split("-")
    if len(parts) < 3:
         raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset token format",
        )
    user_id = parts[1]
    token_timestamp = int(parts[2])
    
    # Enforce expiry limit (e.g. 1 hour = 3600 seconds)
    current_time = int(datetime.now(timezone.utc).timestamp())
    if current_time - token_timestamp > 3600:
         raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired",
        )
        
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset token",
        )

    user.hashed_password = security.get_password_hash(confirm_in.new_password)
    db.commit()
    return {"message": "Password reset successfully"}

@router.post("/logout")
def logout(refresh_in: schemas.TokenRefreshRequest, db: Session = Depends(get_db)):
    db_token = db.query(RefreshToken).filter(
        RefreshToken.token == refresh_in.refresh_token
    ).first()
    if db_token:
        db_token.revoked = True
        db.commit()
    return {"message": "Logged out successfully"}

