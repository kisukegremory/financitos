from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from home.apps.financitos import csv_import, db
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


class CsvFile(BaseModel):
    name: str = ""
    content: str = Field(min_length=1)
    invoice: InvoiceParam | None = None  # padrão: tirado do nome (Nubank_AAAA-MM-DD.csv)


class ImportCsvRequest(BaseModel):
    files: list[CsvFile] = Field(min_length=1)
    source: str = Field(default="Nubank", examples=["Nubank"])
    save: bool = False


class ImportCsvResponse(ParseResponse):
    from_history: int  # descrições cuja caixinha veio de lançamentos já salvos
    from_llm: int  # descrições inéditas enviadas à LLM


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


@router.post("/import/csv")
def import_csv(
    req: ImportCsvRequest,
    conn: Conn,
    categorizer: Annotated[Categorizer, Depends(get_categorizer)],
) -> ImportCsvResponse:
    """Importa um ou mais CSVs do Nubank de uma vez. Datas e valores vêm do arquivo;
    a caixinha vem do histórico e, para descrições inéditas, de uma única chamada à LLM."""
    batches = []
    for f in req.files:
        invoice = f.invoice or csv_import.invoice_from_filename(f.name)
        if not invoice:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"{f.name or 'arquivo'}: informe a fatura (AAAA-MM), não deu para tirar do nome",
            )
        try:
            rows = csv_import.parse_nubank(f.content)
        except csv_import.CsvError as e:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{f.name}: {e}") from e
        batches.append((parse_invoice(invoice), rows))

    all_rows = [r for _, rows in batches for r in rows]
    known = db.known_categories(conn, (r.description for r in all_rows), req.source)
    categories, from_llm = csv_import.categorize(all_rows, known, categorizer)
    items = csv_import.to_transactions(batches, categories, req.source)
    resp = ImportCsvResponse(
        items=items,
        total=sum((t.amount for t in items), start=Decimal(0)),
        from_history=len(known),
        from_llm=from_llm,
    )
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
