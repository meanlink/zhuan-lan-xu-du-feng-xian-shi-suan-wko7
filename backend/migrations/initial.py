from sqlalchemy import inspect, text
from src.config.database import Base, Session, engine
from src import models
from src.models import LedgerAccount
# 旧库升级的幂等补列：新装由 create_all 一次建齐，历史试验默认 fee=0 / none 不追收费
JOB_COLUMNS = {
    'fee': "ALTER TABLE jobs ADD COLUMN fee INTEGER NOT NULL DEFAULT 0",
    'settlement': "ALTER TABLE jobs ADD COLUMN settlement VARCHAR(20) NOT NULL DEFAULT 'none'",
    'idempotency_key': "ALTER TABLE jobs ADD COLUMN idempotency_key VARCHAR(80) NULL",
    'request_hash': "ALTER TABLE jobs ADD COLUMN request_hash VARCHAR(64) NULL",
}
def _has_unique_on(insp, table, column):
    for idx in insp.get_indexes(table):
        if idx.get('unique') and idx.get('column_names') == [column]:
            return True
    return any(uc.get('column_names') == [column] for uc in insp.get_unique_constraints(table))
def migrate():
    Base.metadata.create_all(engine)
    insp = inspect(engine)
    if 'jobs' in insp.get_table_names():
        existing = {c['name'] for c in insp.get_columns('jobs')}
        with engine.begin() as conn:
            for column, ddl in JOB_COLUMNS.items():
                if column not in existing:
                    conn.execute(text(ddl))
        insp = inspect(engine)
        if 'idempotency_key' in {c['name'] for c in insp.get_columns('jobs')} and not _has_unique_on(insp, 'jobs', 'idempotency_key'):
            with engine.begin() as conn:
                conn.execute(text('CREATE UNIQUE INDEX uq_jobs_idempotency_key ON jobs (idempotency_key)'))
    with Session() as db:  # 账本单行账户，主键固定，余额变动全程加行锁
        if not db.get(LedgerAccount, 1):
            db.add(LedgerAccount(id=1, available=0, held=0))
            db.commit()
if __name__=='__main__':migrate()
