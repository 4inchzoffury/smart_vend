from fastapi import HTTPException, Request


def require_user(request: Request) -> dict:
    user = request.session.get("user")
    if not user:
        raise HTTPException(
            status_code=307,
            headers={"Location": f"/login?next={request.url.path}"},
        )
    return user
