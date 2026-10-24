from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, Dict
import jwt
from fastapi import HTTPException, Security, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from src.config import settings
from src.models import User, UserRole, AccessTier

# Pre-seeded enterprise demo identities (DEMO DATA)
DEMO_USERS: Dict[str, User] = {
    "alice.requester@company.internal": User(
        id="usr-alice-01",
        email="alice.requester@company.internal",
        full_name="Alice Chen",
        role=UserRole.REQUESTER,
        department="IT Systems Engineering",
        spending_limit_usd=Decimal("0.00"),
        access_tier=AccessTier.INTERNAL
    ),
    "bob.manager@company.internal": User(
        id="usr-bob-02",
        email="bob.manager@company.internal",
        full_name="Bob Martinez",
        role=UserRole.APPROVER,
        department="Procurement Operations",
        spending_limit_usd=Decimal("5000.00"),
        access_tier=AccessTier.INTERNAL
    ),
    "carol.vp@company.internal": User(
        id="usr-carol-03",
        email="carol.vp@company.internal",
        full_name="Carol Danvers",
        role=UserRole.EXECUTIVE_APPROVER,
        department="Executive Leadership",
        spending_limit_usd=Decimal("100000.00"),
        access_tier=AccessTier.RESTRICTED
    ),
    "mallory.external@vendor.internal": User(
        id="usr-mallory-04",
        email="mallory.external@vendor.internal",
        full_name="Mallory Vance",
        role=UserRole.EXTERNAL_CONTRACTOR,
        department="External Contractor",
        spending_limit_usd=Decimal("0.00"),
        access_tier=AccessTier.PUBLIC
    )
}

security = HTTPBearer(auto_error=False)


def create_access_token(user: User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": user.email,
        "uid": user.id,
        "name": user.full_name,
        "role": user.role.value,
        "dept": user.department,
        "tier": user.access_tier.value,
        "exp": expire
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def get_user_by_email(email: str) -> Optional[User]:
    return DEMO_USERS.get(email.lower().strip())


async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Security(security)) -> User:
    if not credentials or not credentials.credentials:
        # Default to Alice in development when no header is supplied, but flag in logs
        return DEMO_USERS["alice.requester@company.internal"]

    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        email = payload.get("sub")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token: missing subject"
            )
        user = get_user_by_email(email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"User '{email}' not recognized in enterprise directory"
            )
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token has expired. Please sign in again."
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials."
        )


def require_role(allowed_roles: list[UserRole]):
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: role '{current_user.role.value}' lacks required authority. Required: {[r.value for r in allowed_roles]}"
            )
        return current_user
    return role_checker
