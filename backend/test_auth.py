import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import auth_utils, models, database
from database import Base
from datetime import datetime, timedelta

# Create an in-memory SQLite database for unit testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    # Create tables
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        # Drop tables
        Base.metadata.drop_all(bind=engine)

def test_password_hashing():
    password = "super-secret-password"
    hashed = auth_utils.get_password_hash(password)
    
    assert hashed != password
    assert auth_utils.verify_password(password, hashed) is True
    assert auth_utils.verify_password("wrong-password", hashed) is False

def test_jwt_token_generation():
    user_id = "test-user-uuid"
    
    # Test Access Token
    access_token = auth_utils.create_access_token(data={"sub": user_id})
    payload = auth_utils.decode_token(access_token)
    assert payload.get("sub") == user_id
    assert payload.get("type") == "access"
    
    # Test Refresh Token
    refresh_token = auth_utils.create_refresh_token(data={"sub": user_id})
    payload_refresh = auth_utils.decode_token(refresh_token)
    assert payload_refresh.get("sub") == user_id
    assert payload_refresh.get("type") == "refresh"

def test_user_creation_and_query(db_session):
    email = "test@example.com"
    pwd = "my-password"
    hashed = auth_utils.get_password_hash(pwd)
    
    new_user = models.User(email=email, hashed_password=hashed, display_name="Test User")
    db_session.add(new_user)
    db_session.commit()
    db_session.refresh(new_user)
    
    # Query user from DB
    queried_user = db_session.query(models.User).filter(models.User.email == email).first()
    assert queried_user is not None
    assert queried_user.email == email
    assert queried_user.display_name == "Test User"
    assert auth_utils.verify_password(pwd, queried_user.hashed_password) is True

def test_refresh_token_revocation(db_session):
    user_id = "some-user-id"
    token_str = "some-refresh-token-string"
    
    token = models.RefreshToken(
        token=token_str,
        user_id=user_id,
        expires_at=datetime.utcnow() + timedelta(days=7),
    )
    db_session.add(token)
    db_session.commit()
    
    # Check Active
    active_token = db_session.query(models.RefreshToken).filter(
        models.RefreshToken.token == token_str,
        models.RefreshToken.revoked == False
    ).first()
    assert active_token is not None
    
    # Revoke
    active_token.revoked = True
    db_session.commit()
    
    # Verify Revoked
    revoked_token = db_session.query(models.RefreshToken).filter(
        models.RefreshToken.token == token_str,
        models.RefreshToken.revoked == False
    ).first()
    assert revoked_token is None
