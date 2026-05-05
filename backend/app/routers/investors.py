from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.investor import Investor
from app.models.investor_holding import InvestorHolding
from app.schemas.investor import InvestorCreate, InvestorUpdate, InvestorResponse
from app.utils.security import get_password_hash
from app.dependencies import get_current_admin

router = APIRouter()


@router.get("")
def get_investors(
    page: Optional[int] = 1,
    page_size: Optional[int] = 20,
    db: Session = Depends(get_db),
    current_user: Investor = Depends(get_current_admin),
):
    query = db.query(Investor)
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("", response_model=InvestorResponse)
def create_investor(
    investor: InvestorCreate,
    db: Session = Depends(get_db),
    current_user: Investor = Depends(get_current_admin),
):
    db_investor = db.query(Investor).filter(Investor.code == investor.code).first()
    if db_investor:
        raise HTTPException(status_code=400, detail="Investor already exists")

    new_investor = Investor(
        code=investor.code,
        name=investor.name,
        role="viewer",
        phone=investor.phone,
        email=investor.email,
        password_hash=get_password_hash(investor.password),
    )
    db.add(new_investor)
    db.commit()
    db.refresh(new_investor)
    return new_investor


@router.get("/{code}", response_model=InvestorResponse)
def get_investor(
    code: str,
    db: Session = Depends(get_db),
    current_user: Investor = Depends(get_current_admin),
):
    investor = db.query(Investor).filter(Investor.code == code).first()
    if not investor:
        raise HTTPException(status_code=404, detail="Investor not found")
    return investor


@router.put("/{code}", response_model=InvestorResponse)
def update_investor(
    code: str,
    investor: InvestorUpdate,
    db: Session = Depends(get_db),
    current_user: Investor = Depends(get_current_admin),
):
    db_investor = db.query(Investor).filter(Investor.code == code).first()
    if not db_investor:
        raise HTTPException(status_code=404, detail="Investor not found")

    update_data = investor.dict(exclude_unset=True)
    if "password" in update_data:
        update_data["password_hash"] = get_password_hash(update_data.pop("password"))

    for field, value in update_data.items():
        setattr(db_investor, field, value)

    db.commit()
    db.refresh(db_investor)
    return db_investor


@router.delete("/{code}")
def delete_investor(
    code: str,
    db: Session = Depends(get_db),
    current_user: Investor = Depends(get_current_admin),
):
    investor = db.query(Investor).filter(Investor.code == code).first()
    if not investor:
        raise HTTPException(status_code=404, detail="Investor not found")

    # 检查投资人是否仍持有份额
    holding = (
        db.query(InvestorHolding)
        .filter(InvestorHolding.investor_code == code)
        .order_by(InvestorHolding.snapshot_date.desc())
        .first()
    )
    if holding and holding.shares > 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "INVESTOR_HAS_SHARES",
                "message": "投资人仍持有份额，需先全部赎回",
            },
        )

    db.delete(investor)
    db.commit()
    return {"message": "Investor deleted successfully"}
