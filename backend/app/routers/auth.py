from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.investor import Investor
from app.schemas.auth import LoginRequest, LoginResponse, ChangePasswordRequest
from app.utils.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    blacklist_token,
    record_login_failure,
    clear_login_failure,
    is_account_locked,
)
from app.dependencies import (
    get_client_ip,
    get_user_agent,
    record_login_log,
    get_current_user,
    get_current_admin,
)
from datetime import datetime, timedelta
from app.config import get_settings

settings = get_settings()
router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    ip_address = get_client_ip(request)
    user_agent = get_user_agent(request)

    # 1. 查找用户
    investor = db.query(Investor).filter(Investor.code == body.code).first()

    # 2. 检查账户是否已被锁定
    locked, locked_until = is_account_locked(body.code)
    if locked:
        record_login_log(db, body.code, "login_failed", "failed", ip_address, user_agent)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "ACCOUNT_LOCKED",
                "message": f"账户已锁定，请 {locked_until.isoformat()} 后再试",
                "locked_until": locked_until.isoformat(),
            },
        )

    # 3. 验证密码
    if not investor or not verify_password(body.password, investor.password_hash):
        is_now_locked, new_locked_until = record_login_failure(body.code)
        record_login_log(db, body.code, "login_failed", "failed", ip_address, user_agent)

        if is_now_locked:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "ACCOUNT_LOCKED",
                    "message": f"连续登录失败次数过多，账户已锁定至 {new_locked_until.isoformat()}",
                    "locked_until": new_locked_until.isoformat(),
                },
            )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "INVALID_CREDENTIALS",
                "message": "用户名或密码错误",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 4. 登录成功：清除失败记录、更新最后登录时间、记录日志
    clear_login_failure(body.code)
    investor.last_login_at = datetime.utcnow()
    db.commit()
    record_login_log(db, body.code, "login", "success", ip_address, user_agent)

    # 5. 生成 Token
    expires_at = datetime.utcnow() + timedelta(days=settings.token_expire_days)
    token = create_access_token({
        "sub": investor.code,
        "role": investor.role,
    })

    return {
        "token": token,
        "expires_at": expires_at.isoformat(),
        "user": {
            "code": investor.code,
            "name": investor.name,
            "role": investor.role,
        },
    }


@router.post("/logout")
def logout(
    request: Request,
    current_user: Investor = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    登出接口。
    将当前 Token 加入黑名单，并记录登出日志。
    """
    from fastapi.security import HTTPAuthorizationCredentials
    from app.dependencies import security

    credentials: HTTPAuthorizationCredentials = security(request)
    if credentials:
        blacklist_token(credentials.credentials)

    ip_address = get_client_ip(request)
    user_agent = get_user_agent(request)
    record_login_log(db, current_user.code, "logout", "success", ip_address, user_agent)

    return {"message": "登出成功"}


@router.put("/password")
def change_password(
    request: Request,
    body: ChangePasswordRequest,
    current_user: Investor = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    修改密码。
    - admin 可以修改任意用户密码（通过 target_code）
    - viewer 只能修改自己的密码，且必须提供旧密码验证
    """
    ip_address = get_client_ip(request)
    user_agent = get_user_agent(request)

    target_code = body.target_code or current_user.code

    # 权限检查：非 admin 只能修改自己
    if current_user.role != "admin" and target_code != current_user.code:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "FORBIDDEN",
                "message": "无权修改其他用户密码",
            },
        )

    investor = db.query(Investor).filter(Investor.code == target_code).first()
    if not investor:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 非 admin 修改自己密码时，必须验证旧密码
    if current_user.role != "admin" or target_code == current_user.code:
        if not body.old_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "OLD_PASSWORD_REQUIRED",
                    "message": "修改密码需要提供旧密码",
                },
            )
        if not verify_password(body.old_password, investor.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "INVALID_OLD_PASSWORD",
                    "message": "旧密码错误",
                },
            )

    investor.password_hash = get_password_hash(body.new_password)
    db.commit()

    # 修改密码后，将当前 Token 加入黑名单（强制重新登录）
    from fastapi.security import HTTPAuthorizationCredentials
    from app.dependencies import security

    credentials: HTTPAuthorizationCredentials = security(request)
    if credentials:
        blacklist_token(credentials.credentials)

    record_login_log(db, target_code, "password_changed", "success", ip_address, user_agent)

    return {"message": "密码修改成功，请重新登录"}
