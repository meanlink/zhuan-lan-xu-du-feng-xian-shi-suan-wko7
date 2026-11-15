"""预付试算账本：入账、预占、实扣、退回与余额核对。

并发约定：
- 余额变动一律用原子条件 UPDATE（WHERE available>=fee），条件在写锁内
  对最新提交值求值，并发创建不透支，不依赖事务快照；
- 变更请求先进 lock_account 拿账户行写锁，把并发串行化，SQLite 与
  MySQL 行为一致；幂等检查在锁内进行，同号重试安全返回原记录；
- 结算用条件 UPDATE（WHERE settlement='held'），历史任务与迟到的
  旧进程不影响账户，保证不重复扣退。
"""
import csv
import io
import time
from fastapi import HTTPException
from sqlalchemy import select, update, func
from src.models import Job, LedgerAccount, LedgerEntry

KIND_LABELS = {'deposit': '入账', 'hold': '预占', 'charge': '实扣', 'refund': '退回'}
SETTLEMENT_LABELS = {'held': '待结算', 'charged': '已扣款', 'refunded': '已退回', 'none': '历史不计费'}
ACCOUNT_ID = 1


def _ensure_account(db):
    acc = db.get(LedgerAccount, ACCOUNT_ID)
    if acc is None:
        acc = LedgerAccount(id=ACCOUNT_ID, available=0, held=0)
        db.add(acc)
        db.flush()
    return acc


def lock_account(db):
    """账户行写锁（无变化 UPDATE）：变更请求事务内最先调用，串行化并发。"""
    _ensure_account(db)
    db.execute(
        update(LedgerAccount).where(LedgerAccount.id == ACCOUNT_ID)
        .values(available=LedgerAccount.available)
        .execution_options(synchronize_session=False)
    )


def _account(db):
    return db.scalar(
        select(LedgerAccount).where(LedgerAccount.id == ACCOUNT_ID)
        .execution_options(populate_existing=True)
    )


def _entry(db, kind, amount, acc, actor, job_id=None, note='', request_key=None):
    e = LedgerEntry(kind=kind, amount=amount, available_after=acc.available, held_after=acc.held,
                    job_id=job_id, actor=actor, note=note[:290], request_key=request_key, created_at=time.time())
    db.add(e)
    db.flush()
    return e


def by_request_key(db, request_key):
    if not request_key:
        return None
    return db.scalar(select(LedgerEntry).where(LedgerEntry.request_key == request_key))


def deposit(db, amount, actor, note='', request_key=None):
    """管理员登记入账。同一 request_key 重试返回原流水，不重复入账。"""
    if amount < 1:
        raise HTTPException(422, '入账额度必须为正整数')
    lock_account(db)
    if request_key:
        existing = by_request_key(db, request_key)
        if existing:
            return existing, False
    db.execute(
        update(LedgerAccount).where(LedgerAccount.id == ACCOUNT_ID)
        .values(available=LedgerAccount.available + amount)
        .execution_options(synchronize_session=False)
    )
    return _entry(db, 'deposit', amount, _account(db), actor, note=note or '管理员登记入账', request_key=request_key), True


def hold(db, fee):
    """原子条件预占：available>=fee 才扣减，否则整笔拒绝（调用方须在同事务内落库试验）。

    返回记账后的账户行，流水在试验落库拿到 id 后由 record_hold 补记。
    """
    result = db.execute(
        update(LedgerAccount).where(LedgerAccount.id == ACCOUNT_ID, LedgerAccount.available >= fee)
        .values(available=LedgerAccount.available - fee, held=LedgerAccount.held + fee)
        .execution_options(synchronize_session=False)
    )
    acc = _account(db)
    if result.rowcount != 1:
        raise HTTPException(409, f'试算额度不足：本次需 {fee} 额度（每条样本 1 额度），当前可用 {acc.available}，请业务负责人先登记入账。')
    return acc


def record_hold(db, acc, job, actor):
    return _entry(db, 'hold', job.fee, acc, actor, job_id=job.id, note=f'创建试验预占 · {job.name}')


def settle(db, job, success):
    """与结果落定同事务结算：成功实扣，失败退回预占。

    条件更新 settlement held→charged/refunded：历史任务（none）与已被
    其他进程结算的迟到调用不影响账户，保证同成同败、不重复扣退。
    """
    target = 'charged' if success else 'refunded'
    result = db.execute(
        update(Job).where(Job.id == job.id, Job.settlement == 'held').values(settlement=target)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        return None
    job.settlement = target
    values = {'held': LedgerAccount.held - job.fee}
    if not success:
        values['available'] = LedgerAccount.available + job.fee
    db.execute(
        update(LedgerAccount).where(LedgerAccount.id == ACCOUNT_ID).values(**values)
        .execution_options(synchronize_session=False)
    )
    note = f'试算完成实扣 · {job.name}' if success else f'计算失败退回预占 · {job.name}'
    return _entry(db, 'charge' if success else 'refund', job.fee, _account(db), 'worker', job_id=job.id, note=note)


def summary(db):
    acc = db.get(LedgerAccount, ACCOUNT_ID)
    available = acc.available if acc else 0
    held = acc.held if acc else 0

    def total(kind):
        return db.scalar(select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(LedgerEntry.kind == kind))

    pending = db.scalar(select(func.count()).select_from(Job).where(Job.settlement == 'held'))
    return {'available': available, 'held': held, 'deposited': total('deposit'),
            'charged': total('charge'), 'refunded': total('refund'), 'pending_jobs': pending}


def list_entries(db, limit=200):
    rows = list(db.scalars(select(LedgerEntry).order_by(LedgerEntry.id.desc()).limit(limit)))
    job_ids = {e.job_id for e in rows if e.job_id}
    jobs = {j.id: j for j in db.scalars(select(Job).where(Job.id.in_(job_ids)))} if job_ids else {}
    return rows, jobs


def _safe(v):
    text = str(v if v is not None else '')
    return "'" + text if text.startswith(('=', '+', '-', '@', '\t', '\r')) else text


def entries_csv(db):
    rows, jobs = list_entries(db, 5000)
    out = io.StringIO()
    out.write('﻿')
    writer = csv.writer(out)
    writer.writerow(['流水号', '时间', '类型', '额度', '可用余额', '预占余额', '关联试验', '试验结算', '操作者', '备注'])
    for e in reversed(rows):  # 按时间正序，便于逐笔核对余额
        job = jobs.get(e.job_id)
        writer.writerow([e.id, time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(e.created_at)),
                         KIND_LABELS.get(e.kind, e.kind), e.amount, e.available_after, e.held_after,
                         _safe(job.name if job else ''), SETTLEMENT_LABELS.get(job.settlement if job else '', ''),
                         _safe(e.actor), _safe(e.note)])
    return out.getvalue()
