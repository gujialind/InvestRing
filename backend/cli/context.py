"""
CLI 执行上下文

提供统一的 DB session 管理和异常捕获。
"""
import sys
import traceback
from contextlib import contextmanager
from typing import Generator

from sqlalchemy.exc import IntegrityError

from cli.output import error


@contextmanager
def cli_context() -> Generator:
    """
    CLI 命令执行上下文管理器

    用法：
        with cli_context() as db:
            # db 操作
            ...

    行为：
    - 创建 SessionLocal session
    - 成功时 commit + close
    - ValueError -> VALIDATION_ERROR + exit(1)
    - IntegrityError -> ALREADY_EXISTS + exit(1)
    - 其他异常 -> INTERNAL_ERROR + exit(2)
    """
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        yield db
        db.commit()
    except SystemExit:
        # 允许 output.success/error 的 sys.exit 正常传播
        db.close()
        raise
    except ValueError as e:
        db.rollback()
        db.close()
        error("VALIDATION_ERROR", str(e))
    except IntegrityError as e:
        db.rollback()
        db.close()
        error("ALREADY_EXISTS", f"数据库约束冲突: {e.orig}")
    except Exception as e:
        db.rollback()
        db.close()
        # 输出堆栈信息到 stderr 供调试
        traceback.print_exc(file=sys.stderr)
        error("INTERNAL_ERROR", str(e))
    else:
        db.close()
