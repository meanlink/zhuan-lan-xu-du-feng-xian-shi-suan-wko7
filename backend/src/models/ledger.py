from sqlalchemy import String, Integer, Double, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base
class LedgerAccount(Base):
    __tablename__ = 'ledger_account'
    id: Mapped[int] = mapped_column(primary_key=True)
    available: Mapped[int] = mapped_column(Integer, default=0)
    held: Mapped[int] = mapped_column(Integer, default=0)
class LedgerEntry(Base):
    __tablename__ = 'ledger_entries'
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))  # deposit入账 / hold预占 / charge实扣 / refund退回
    amount: Mapped[int] = mapped_column(Integer)
    available_after: Mapped[int] = mapped_column(Integer)
    held_after: Mapped[int] = mapped_column(Integer)
    job_id: Mapped[int | None] = mapped_column(ForeignKey('jobs.id'), nullable=True)
    actor: Mapped[str] = mapped_column(String(150))
    note: Mapped[str] = mapped_column(String(300), default='')
    request_key: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)
    created_at: Mapped[float] = mapped_column(Double)
