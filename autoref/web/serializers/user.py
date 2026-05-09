from collections.abc import Sequence
from typing import TYPE_CHECKING

from ..schemas.user import AccountResponse, UserResponse

if TYPE_CHECKING:
    from ...core.auth import User


def user_row_to_response(row: Sequence) -> UserResponse:
    """Map a DB row tuple (id, osu_user_id, osu_username, role, irc_username, created_at) to UserResponse."""
    return UserResponse(
        id=row[0],
        osu_user_id=row[1],
        osu_username=row[2],
        role=row[3],
        irc_username=row[4],
        created_at=row[5],
    )


def user_to_account_response(user: "User") -> AccountResponse:
    """Map a User dataclass to AccountResponse (self-view with irc_set)."""
    return AccountResponse(
        id=user.id,
        osu_user_id=user.osu_user_id,
        osu_username=user.osu_username,
        role=user.role,
        irc_username=user.irc_username,
        irc_set=bool(user.irc_username and user.irc_password),
    )
