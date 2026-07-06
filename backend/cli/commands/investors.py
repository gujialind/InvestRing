"""
ir investor - 投资人管理命令组
"""
import typer
from typing import Optional

from cli.context import cli_context
from cli.output import success, error
from cli.utils import serialize_model, paginate, pagination_meta

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_investors(
    page: int = typer.Option(1, "--page", help="页码"),
    page_size: int = typer.Option(20, "--page-size", help="每页数量"),
    all: bool = typer.Option(False, "--all", help="获取全部"),
):
    """获取投资人列表"""
    with cli_context() as db:
        from app.models.investor import Investor

        query = db.query(Investor).order_by(Investor.created_at.desc())
        items, total, page, page_size = paginate(query, page, page_size, all)
        success(
            data=[serialize_model(i, exclude=["password_hash"]) for i in items],
            meta=pagination_meta(total, page, page_size),
        )


@app.command("create")
def create_investor(
    code: str = typer.Option(..., "--code", help="投资人代码"),
    name: str = typer.Option(..., "--name", help="投资人姓名"),
    password: str = typer.Option(..., "--password", help="密码"),
    phone: Optional[str] = typer.Option(None, "--phone", help="手机号"),
    email: Optional[str] = typer.Option(None, "--email", help="邮箱"),
    role: str = typer.Option("viewer", "--role", help="角色: admin/viewer"),
):
    """创建投资人"""
    with cli_context() as db:
        from app.models.investor import Investor
        from app.utils.security import get_password_hash

        existing = db.query(Investor).filter(Investor.code == code).first()
        if existing:
            error("ALREADY_EXISTS", f"投资人 {code} 已存在")

        investor = Investor(
            code=code, name=name, role=role, phone=phone, email=email,
            password_hash=get_password_hash(password),
        )
        db.add(investor)
        db.flush()
        db.refresh(investor)
        success(data=serialize_model(investor, exclude=["password_hash"]))


@app.command("get")
def get_investor(
    code: str = typer.Argument(..., help="投资人代码"),
):
    """查看投资人详情"""
    with cli_context() as db:
        from app.models.investor import Investor

        investor = db.query(Investor).filter(Investor.code == code).first()
        if not investor:
            error("NOT_FOUND", f"投资人 {code} 不存在")
        success(data=serialize_model(investor, exclude=["password_hash"]))


@app.command("update")
def update_investor(
    code: str = typer.Argument(..., help="投资人代码"),
    name: Optional[str] = typer.Option(None, "--name", help="姓名"),
    role: Optional[str] = typer.Option(None, "--role", help="角色"),
    phone: Optional[str] = typer.Option(None, "--phone", help="手机号"),
    email: Optional[str] = typer.Option(None, "--email", help="邮箱"),
    password: Optional[str] = typer.Option(None, "--password", help="新密码"),
):
    """更新投资人信息"""
    with cli_context() as db:
        from app.models.investor import Investor
        from app.utils.security import get_password_hash

        investor = db.query(Investor).filter(Investor.code == code).first()
        if not investor:
            error("NOT_FOUND", f"投资人 {code} 不存在")

        if name is not None:
            investor.name = name
        if role is not None:
            investor.role = role
        if phone is not None:
            investor.phone = phone
        if email is not None:
            investor.email = email
        if password is not None:
            investor.password_hash = get_password_hash(password)

        db.flush()
        db.refresh(investor)
        success(data=serialize_model(investor, exclude=["password_hash"]))


@app.command("delete")
def delete_investor(
    code: str = typer.Argument(..., help="投资人代码"),
    yes: bool = typer.Option(False, "--yes", help="跳过确认"),
):
    """删除投资人（持有份额时禁止删除）"""
    with cli_context() as db:
        from app.models.investor import Investor
        from app.models.investor_holding import InvestorHolding

        investor = db.query(Investor).filter(Investor.code == code).first()
        if not investor:
            error("NOT_FOUND", f"投资人 {code} 不存在")

        # 检查是否持有份额
        holding = (
            db.query(InvestorHolding)
            .filter(InvestorHolding.investor_code == code)
            .order_by(InvestorHolding.snapshot_date.desc())
            .first()
        )
        if holding and holding.shares and holding.shares > 0:
            error("INVESTOR_HAS_SHARES", "投资人仍持有份额，请先全部赎回")

        db.delete(investor)
        db.flush()
        success(data={"message": f"投资人 {code} 已删除"})
