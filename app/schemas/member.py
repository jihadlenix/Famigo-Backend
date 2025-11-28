from .common import ORMModel
class MemberOut(ORMModel):
    id: str
    family_id: str
    user_id: str
    role: str
    display_name: str | None = None
    avatar_url: str | None = None
    wallet_balance: int = 0  # Points/coins balance for this member
    username: str | None = None  # Username from User model
    profile_pic: str | None = None  # Profile picture from User model
    full_name: str | None = None  # Full name from User model
    email: str | None = None  # Email from User model (for fallback display)
