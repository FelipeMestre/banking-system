"""Statement PDF rendering (Credit Cards Phase 4).

Pure formatting — renders period, due date, totals and line items from
already-computed values. Performs no business computation: everything here
was already decided by `domain/service/statement_service.py`.
"""
from __future__ import annotations

from io import BytesIO
from typing import Iterable, Sequence

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

from ...domain.model import CardMovement, Installment, Statement


def render(
    statement: Statement,
    movements: Sequence[CardMovement],
    installments: Iterable[Installment],
) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=LETTER)
    _, height = LETTER

    y = height - 72
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(72, y, "Credit Card Statement")

    y -= 24
    pdf.setFont("Helvetica", 10)
    for label, value in (
        ("Period", f"{statement.period_start.isoformat()} - {statement.period_end.isoformat()}"),
        ("Due date", statement.due_date.isoformat()),
        ("Purchases total", f"{statement.purchases_total:.2f}"),
        ("Interest total", f"{statement.interest_total:.2f}"),
        ("Late fees total", f"{statement.late_fees_total:.2f}"),
        ("Total due", f"{statement.total_due:.2f}"),
        ("Minimum payment", f"{statement.minimum_payment:.2f}"),
        ("Credit balance carried", f"{statement.credit_balance:.2f}"),
    ):
        pdf.drawString(72, y, f"{label}: {value}")
        y -= 16

    y -= 8
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(72, y, "Movements")
    y -= 16
    pdf.setFont("Helvetica", 9)
    for movement in movements:
        pdf.drawString(72, y, f"{movement.movement_type.value}: {movement.amount:.2f}")
        y -= 14

    y -= 8
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(72, y, "Installments billed this period")
    y -= 16
    pdf.setFont("Helvetica", 9)
    for installment in installments:
        pdf.drawString(72, y, f"#{installment.installment_number}: {installment.amount:.2f}")
        y -= 14

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
