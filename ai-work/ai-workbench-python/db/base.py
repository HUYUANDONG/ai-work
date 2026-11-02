"""
SQLAlchemy DeclarativeBase。

业务 Entity 暂不建；Checkpoint 表由官方 Checkpointer 自管。
预留 Base 便于后续本地辅助表扩展。
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """ORM 声明基类（当前无业务 Model）。"""
