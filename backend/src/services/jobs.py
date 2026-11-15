import time
from fastapi import HTTPException
from redis import Redis
from sqlalchemy import select
from src.config.settings import REDIS_URL
from src.models import Dataset, Job
from src.services.business import metadata
from src.services import ledger
from src.utils.serialization import checksum
def _validate_params(db, data):
    allowed={p['key']:p for p in metadata().get('parameters',[])}
    if set(data.params)-set(allowed): raise HTTPException(422,'包含未知分析参数')
    params={k:p['default'] for k,p in allowed.items()}
    params.update(data.params)
    for key,p in allowed.items():
        v=params[key]
        if p['type']=='number':
            try:
                v=float(v)
                if not (p.get('min',-1e9)<=v<=p.get('max',1e9)): raise ValueError()
                params[key]=v
            except (ValueError,TypeError): raise HTTPException(422, f'{p["label"]} 超出范围或非数值')
        elif str(v) not in [str(o['value']) for o in p.get('options',[])]:
            raise HTTPException(422,f'{p["label"]} 不是有效选项')
    return params
def create(db, data, user, header_key=None):
    """创建试验：固定费用=样本条数，预占余额，不足整笔拒绝。

    同一请求号重试返回已建试验（不重复扣款）；同号换内容整笔拒绝。
    账户行写锁把并发创建串行化，原子条件预占保证不透支。
    """
    ledger.lock_account(db)  # 串行点：并发请求在此排队
    d=db.get(Dataset,data.dataset_id)
    if not d: raise HTTPException(404,'数据批次不存在')
    params=_validate_params(db,data)
    fee=len(d.records)
    request_key=((data.request_id or header_key or '').strip() or None)
    if request_key and len(request_key)>80: raise HTTPException(422,'请求号最长80个字符')
    request_hash=checksum({'name':data.name,'dataset_id':data.dataset_id,'params':params})
    if request_key:
        existing=db.scalar(select(Job).where(Job.idempotency_key==request_key))
        if existing:
            if existing.request_hash!=request_hash:
                raise HTTPException(409,'同一请求号提交了不同的试验内容，已整笔拒绝')
            return existing,False  # 重试：不重复建试验、不重复扣款
    acc=ledger.hold(db,fee)
    j=Job(name=data.name,dataset_id=data.dataset_id,params=params,created_by=user.id,created_at=time.time(),status='queued',fee=fee,settlement='held',idempotency_key=request_key,request_hash=request_hash)
    db.add(j); db.flush()
    ledger.record_hold(db,acc,j,user.email)
    return j,True
def replay(db,request_key):
    if not request_key: return None
    return db.scalar(select(Job).where(Job.idempotency_key==request_key))
def replay_checked(db,data,request_key):
    """撞号兜底重查：返回 (已建试验, 内容是否一致)，用于区分重试与同号换内容。"""
    j=replay(db,request_key)
    if j is None: return None,False
    params=_validate_params(db,data)
    h=checksum({'name':data.name,'dataset_id':data.dataset_id,'params':params})
    return j,j.request_hash==h
def enqueue(job_id):
    try:
        r=Redis.from_url(REDIS_URL); r.rpush('analysis:queue',job_id); r.close()
    except Exception:
        pass # SQL queued status is the durable fallback
