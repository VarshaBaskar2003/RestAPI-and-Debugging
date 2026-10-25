import logging
import re
from datetime import date
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("expense_tracker")

app = FastAPI(title="Expense Tracker API")

expenses = {
    1: {"id": 1, "description": "Travel", "amount": 450.0, "category": "Travel", "expense_date": "2026-10-01"},
    2: {"id": 2, "description": "Lunch", "amount": 180.0, "category": "Food", "expense_date": "2026-10-02"},
}
next_id = 3



def validate_expense_date(value):
    if value is None:  
        return value
    
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("expense_date must use YYYY-MM-DD format")
    try:
        date.fromisoformat(value)  
    except ValueError:
        raise ValueError("expense_date must be a valid calendar date")
    return value


class ExpenseCreate(BaseModel):
  
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    description: str = Field(min_length=1, max_length=200)
    amount: float = Field(gt=0, le=1_000_000_000, allow_inf_nan=False)
    category: str = Field(min_length=1, max_length=50)
    expense_date: str

    @field_validator("expense_date")
    @classmethod
    def check_expense_date(cls, value):
        return validate_expense_date(value)


class ExpenseUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    description: str | None = Field(default=None, min_length=1, max_length=200)
    amount: float | None = Field(default=None, gt=0, le=1_000_000_000, allow_inf_nan=False)
    category: str | None = Field(default=None, min_length=1, max_length=50)
    expense_date: str | None = None

    @field_validator("expense_date")
    @classmethod
    def check_expense_date(cls, value):
        return validate_expense_date(value)




def validation_error(details):
    return JSONResponse(status_code=400, content={"error": "Validation failed", "details": details})


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError):
    details = []
    for err in exc.errors():
        field = ".".join(str(part) for part in err["loc"] if part != "body")
        message = err["msg"].removeprefix("Value error, ")
        details.append(f"{field}: {message}" if field else message)
    return validation_error(details)


@app.exception_handler(StarletteHTTPException)
async def handle_http_error(request: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail}, headers=exc.headers)


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception):
    # Full traceback goes to the server log only, never to the client.
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"error": "Internal server error"})


@app.get("/")
def health():
    return {"message": "Expense Tracker API is running"}


@app.get("/expenses")
def list_expenses(category: str | None = None):
    results = list(expenses.values())
    if category and category.strip():
        wanted = category.strip().casefold()
        results = [e for e in results if e["category"].casefold() == wanted]
    return results


@app.get("/expenses/summary")
def expense_summary():
    total = sum(e["amount"] for e in expenses.values())
    return {
        "count": len(expenses),
        "total_amount": round(total, 2),
    }


@app.get("/expenses/{expense_id}")
def get_expense(expense_id: int):
    if expense_id not in expenses:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expenses[expense_id]


@app.post("/expenses", status_code=201)
def create_expense(payload: ExpenseCreate):
    global next_id
    expense = {
        "id": next_id,
        "description": payload.description,
        "amount": round(payload.amount, 2),
        "category": payload.category,
        "expense_date": payload.expense_date,
    }
    expenses[next_id] = expense
    next_id += 1
    return expense


@app.put("/expenses/{expense_id}")
def update_expense(expense_id: int, payload: ExpenseUpdate):
    if expense_id not in expenses:
        raise HTTPException(status_code=404, detail="Expense not found")

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return validation_error(["at least one field must be provided"])


    null_fields = [name for name, value in updates.items() if value is None]
    if null_fields:
        return validation_error([f"{name} cannot be null" for name in null_fields])

    if "amount" in updates:
        updates["amount"] = round(updates["amount"], 2)
    expenses[expense_id].update(updates)
    return expenses[expense_id]


@app.delete("/expenses/{expense_id}", status_code=204)
def delete_expense(expense_id: int):
    if expense_id not in expenses:
        raise HTTPException(status_code=404, detail="Expense not found")
    del expenses[expense_id]
    return Response(status_code=204)