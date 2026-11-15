from pydantic import BaseModel, Field
class DepositInput(BaseModel):
    amount: int = Field(ge=1, le=1000000)
    note: str = Field(default='', max_length=200)
    request_id: str | None = Field(default=None, max_length=80)
