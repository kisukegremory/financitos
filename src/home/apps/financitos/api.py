from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from home.apps.financitos import db
from home.apps.financitos.llm import Categorizer
from home.apps.financitos.models import (
    Balance,
    BalanceIn,
    Category,
    InvoiceSummary,
    Payment,
    PaymentIn,
    StoredTransaction,
    Transaction,
    TransactionUpdate,
    parse_invoice,
)
from home.core.config import Settings, get_settings
from home.core.deps import Conn

INVOICE_PATTERN = r"^\d{4}-\d{2}$"


def get_categorizer(settings: Annotated[Settings, Depends(get_settings)]) -> Categorizer:
    return Categorizer(settings)


InvoiceParam = Annotated[str, Field(pattern=INVOICE_PATTERN, examples=["2026-10"])]

router = APIRouter(tags=["financitos"])


class ParseRequest(BaseModel):
    text: str = Field(min_length=1)
    source: str = Field(examples=["PicPay"])
    invoice: InvoiceParam
    save: bool = False


class ParseResponse(BaseModel):
    items: list[Transaction]
    total: Decimal
    inserted: int | None = None
    skipped: int | None = None


class BulkResult(BaseModel):
    inserted: int
    skipped: int


class PayRequest(BaseModel):
    source: str = Field(examples=["PicPay"])
    paid_at: date | None = None


def _not_found(id: int) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"lançamento {id} não encontrado")


@router.get("/categories")
def categories() -> list[str]:
    return [c.value for c in Category]


@router.post("/parse")
def parse(
    req: ParseRequest, conn: Conn, categorizer: Annotated[Categorizer, Depends(get_categorizer)]
) -> ParseResponse:
    invoice = parse_invoice(req.invoice)
    parsed = categorizer.parse(req.text, invoice)
    items = [
        Transaction(**i.model_dump(), source=req.source, invoice=invoice) for i in parsed.items
    ]
    resp = ParseResponse(items=items, total=sum((t.amount for t in items), start=Decimal(0)))
    if req.save:
        result = db.save(conn, items)
        resp.inserted, resp.skipped = result.inserted, result.skipped
    return resp


@router.get("/transactions")
def list_transactions(
    conn: Conn,
    invoice: Annotated[str | None, Query(pattern=INVOICE_PATTERN)] = None,
    source: str | None = None,
    category: Category | None = None,
) -> list[StoredTransaction]:
    return db.list_transactions(conn, parse_invoice(invoice) if invoice else None, source, category)


@router.post("/transactions", status_code=status.HTTP_201_CREATED)
def create_transaction(t: Transaction, conn: Conn) -> StoredTransaction:
    return db.create(conn, t)


@router.post("/transactions/bulk")
def bulk_create(items: list[Transaction], conn: Conn) -> BulkResult:
    """Salva lançamentos revisados (ex.: saída do /parse), ignorando duplicatas."""
    result = db.save(conn, items)
    return BulkResult(inserted=result.inserted, skipped=result.skipped)


@router.get("/transactions/{id}")
def get_transaction(id: int, conn: Conn) -> StoredTransaction:
    found = db.get(conn, id)
    if found is None:
        raise _not_found(id)
    return found


@router.put("/transactions/{id}")
def update_transaction(id: int, changes: TransactionUpdate, conn: Conn) -> StoredTransaction:
    updated = db.update(conn, id, changes)
    if updated is None:
        raise _not_found(id)
    return updated


@router.delete("/transactions/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(id: int, conn: Conn) -> None:
    if not db.delete(conn, id):
        raise _not_found(id)


@router.get("/invoices/{invoice}/summary")
def invoice_summary(
    invoice: Annotated[str, Path(pattern=INVOICE_PATTERN)], conn: Conn, source: str | None = None
) -> InvoiceSummary:
    return db.summary(conn, parse_invoice(invoice), source)


@router.post("/invoices/{invoice}/pay", status_code=status.HTTP_201_CREATED)
def pay_invoice(
    invoice: Annotated[str, Path(pattern=INVOICE_PATTERN)], req: PayRequest, conn: Conn
) -> list[Payment]:
    """Paga o que falta de cada caixinha (pagamento antecipado ou complemento)."""
    return db.pay_remaining(conn, parse_invoice(invoice), req.source, req.paid_at)


@router.get("/payments")
def list_payments(
    conn: Conn,
    invoice: Annotated[str | None, Query(pattern=INVOICE_PATTERN)] = None,
    source: str | None = None,
) -> list[Payment]:
    return db.list_payments(conn, parse_invoice(invoice) if invoice else None, source)


@router.post("/payments", status_code=status.HTTP_201_CREATED)
def create_payment(p: PaymentIn, conn: Conn) -> Payment:
    return db.add_payment(conn, p)


@router.delete("/payments/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_payment(id: int, conn: Conn) -> None:
    if not db.delete_payment(conn, id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"pagamento {id} não encontrado")


@router.get("/balances")
def list_balances(conn: Conn) -> list[Balance]:
    return db.list_balances(conn)


@router.put("/balances/{category}")
def set_balance(category: Category, body: BalanceIn, conn: Conn) -> Balance:
    return db.set_balance(conn, category, body.amount)
