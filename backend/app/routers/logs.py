from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.login_log import LoginLog
from app.models.audit_log import AuditLog
from app.models.system_error_log import SystemErrorLog
from app.schemas.log import LoginLogResponse, AuditLogResponse, SystemErrorLogResponse
from app.dependencies import get_current_admin

router = APIRouter()


def _paginated_response(query, page: int, page_size: int):
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/login")
def get_login_logs(
    page: Optional[int] = 1,
    page_size: Optional[int] = 20,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    query = db.query(LoginLog).order_by(LoginLog.created_at.desc())
    return _paginated_response(query, page, page_size)


@router.get("/audit")
def get_audit_logs(
    page: Optional[int] = 1,
    page_size: Optional[int] = 20,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    query = db.query(AuditLog).order_by(AuditLog.created_at.desc())
    return _paginated_response(query, page, page_size)


@router.get("/error")
def get_error_logs(
    page: Optional[int] = 1,
    page_size: Optional[int] = 20,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    query = db.query(SystemErrorLog).order_by(SystemErrorLog.created_at.desc())
    return _paginated_response(query, page, page_size)
