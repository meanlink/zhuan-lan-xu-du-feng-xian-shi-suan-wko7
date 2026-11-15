from fastapi import APIRouter, Depends, HTTPException, Header, Response
from fastapi.responses import Response as RawResponse
from sqlalchemy.exc import IntegrityError
from src.config.database import get_db
from src.schemas.ledger import DepositInput
from src.middlewares.auth import current_user, admin_only
from src.services import ledger
from src.services.audit import record
from src.utils.serialization import entry_dict
router=APIRouter(prefix='/ledger')
@router.get('/summary')
def summary(db=Depends(get_db),u=Depends(current_user)):
    return ledger.summary(db)
@router.get('/entries')
def entries(limit:int=200,db=Depends(get_db),u=Depends(current_user)):
    rows,jobs=ledger.list_entries(db,max(1,min(limit,1000)))
    return [entry_dict(e,jobs.get(e.job_id)) for e in rows]
@router.get('/export')
def export(db=Depends(get_db),u=Depends(current_user)):
    return RawResponse(ledger.entries_csv(db),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="ledger-entries.csv"'})
@router.post('/deposits',status_code=201)
def deposit(data:DepositInput,response:Response,idempotency_key:str|None=Header(None),db=Depends(get_db),u=Depends(admin_only)):
    key=(data.request_id or idempotency_key or '').strip() or None
    if key and len(key)>80: raise HTTPException(422,'请求号最长80个字符')
    try:
        entry,created=ledger.deposit(db,data.amount,u.email,note=data.note,request_key=key)
        if created: record(db,u.email,'ledger.deposit',{'id':entry.id,'amount':entry.amount})
        db.commit()
    except IntegrityError:
        db.rollback()
        entry=ledger.by_request_key(db,key)
        if entry is None: raise HTTPException(409,'请求号与已有流水冲突，请更换请求号')
        created=False
    if not created: response.status_code=200  # 同一请求重试：返回原流水，不重复入账
    return entry_dict(entry)
