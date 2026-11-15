import time, uuid
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from redis import Redis
from src.config.settings import REDIS_URL
class RequestControl(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = uuid.uuid4().hex[:12]
        if request.url.path != '/health':
            try:
                r=Redis.from_url(REDIS_URL, socket_timeout=1)
                key='rate:'+str(request.client.host)+':'+str(int(time.time()//60))
                n=r.incr(key)
                if n==1: r.expire(key, 65)
                r.close()
                if n>240: return JSONResponse({'detail':'请求过于频繁，请稍后重试'},status_code=429)
            except Exception:
                pass
        response=await call_next(request)
        response.headers['X-Request-ID']=request_id
        response.headers['X-Content-Type-Options']='nosniff'
        return response
