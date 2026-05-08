from fastapi import Depends, HTTPException, Request
from ..core.auth import User, current_user


async def require_login(request: Request) -> User:
    user = current_user(request, request.app.state.db)
    if user is None:
        raise HTTPException(status_code=401, detail="login required")
    return user


def require_role(role: str):
    async def _dep(user: User = Depends(require_login)) -> User:
        if user.role != role:
            raise HTTPException(status_code=403, detail="forbidden")
        return user
    return _dep
