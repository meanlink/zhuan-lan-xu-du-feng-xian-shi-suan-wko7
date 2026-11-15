from fastapi import APIRouter, Depends, HTTPException, Header, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from src.config.database import get_db
from src.models import Job
from src.schemas.job import JobInput
from src.middlewares.auth import current_user, can_write, admin_only
from src.services import jobs
from src.services.audit import record
from src.utils.serialization import job_dict
router=APIRouter(prefix='/jobs')
@router.get('')
def listing(db=Depends(get_db),u=Depends(current_user)):
    return [job_dict(j) for j in db.scalars(select(Job).order_by(Job.id.desc()).limit(100))]
@router.post('',status_code=201)
def create(data:JobInput,response:Response,idempotency_key:str|None=Header(None),db=Depends(get_db),u=Depends(can_write)):
    try:
        j,created=jobs.create(db,data,u,idempotency_key)
        if created: record(db,u.email,'job.create',{'id':j.id,'params':j.params,'fee':j.fee})
        db.commit()
    except IntegrityError:
        db.rollback()  # 唯一请求号兜底：并发撞号时整笔回滚，返回已建试验
        j,same=jobs.replay_checked(db,data,data.request_id or idempotency_key)
        if j is None: raise HTTPException(409,'请求号与已有试验冲突，请更换请求号')
        if not same: raise HTTPException(409,'同一请求号提交了不同的试验内容，已整笔拒绝')
        created=False
    if created: jobs.enqueue(j.id)
    else: response.status_code=200  # 同一请求重试：不重复建试验、不重复扣款
    return job_dict(j)
@router.get('/{id}')
def detail(id:int,db=Depends(get_db),u=Depends(current_user)):
    j=db.get(Job,id)
    if not j: raise HTTPException(404,'分析任务不存在')
    return job_dict(j)
@router.post('/{id}/approve')
def approve(id:int,db=Depends(get_db),u=Depends(admin_only)):
    j=db.get(Job,id)
    if not j: raise HTTPException(404,'分析任务不存在')
    if j.status!='completed':raise HTTPException(409,'仅已完成结果可以批准')
    j.approved=True; record(db,u.email,'job.approve',{'id':id}); db.commit()
    return job_dict(j)
