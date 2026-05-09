from typing import TypedDict


class UserResponse(TypedDict, total=False):
    id: int
    osu_user_id: int | None
    osu_username: str
    role: str
    irc_username: str | None
    created_at: int | None


class AccountResponse(TypedDict):
    id: int
    osu_user_id: int | None
    osu_username: str
    role: str
    irc_username: str | None
    irc_set: bool
