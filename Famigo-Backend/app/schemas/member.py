from .common import ORMModel
class MemberOut(ORMModel):
    id: str
    family_id: str
    user_id: str
    role: str
    display_name: str | None = None
    avatar_url: str | None = None
