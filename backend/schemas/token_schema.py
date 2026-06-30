from pydantic import BaseModel

class UserLoginInfo(BaseModel):
    id: int
    email: str
    full_name: str | None = None
    role: str

class Token(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str
    user: UserLoginInfo

class TokenData(BaseModel):
    email: str | None = None
