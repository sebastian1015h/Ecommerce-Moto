from io import BytesIO
from threading import Lock
from xml.sax.saxutils import escape

import pypdfium2
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.accessories.pricing import price

PDF_RENDER_LOCK = Lock()


def invoice_preview_image(pdf_bytes):
    output = BytesIO()
    # PDFium calls must be serialized across FastAPI worker threads.
    with PDF_RENDER_LOCK:
        document = pypdfium2.PdfDocument(pdf_bytes)
        try:
            document[0].render(scale=1.5).to_pil().save(output, "WEBP", lossless=True)
        finally:
            document.close()
    return output.getvalue()


def invoice_preview(summary):
    output = BytesIO()
    document = SimpleDocTemplate(
        output, pagesize=A4, title="Vista previa de factura | Moto Garaje",
        author="Moto Garaje", leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36,
    )
    styles = getSampleStyleSheet()
    normal = styles["BodyText"]
    title = ParagraphStyle("InvoiceTitle", parent=styles["Title"], alignment=0, fontSize=24, leading=28)
    money = ParagraphStyle("InvoiceMoney", parent=normal, alignment=TA_RIGHT)
    rows = [["Accesorio", "Cant.", "Precio unitario", "Importe"]]
    for line in summary["lines"]:
        product = line["product"]
        variant = product.get("variant")
        name = product["name"] if not variant or variant == "Única" else f"{product['name']} · {variant}"
        rows.append([
            Paragraph(escape(name), normal), str(line["qty"]),
            Paragraph(price(product["price_cop"]), money), Paragraph(price(line["total"]), money),
        ])
    items = Table(rows, colWidths=[document.width - 236, 44, 96, 96], repeatRows=1, hAlign="LEFT")
    items.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#302c26")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f5f2ec"), colors.white]),
    ]))
    taxes = Table([
        ["Subtotal sin IVA", price(summary["subtotal"])],
        [f"IVA ({summary['iva_rate']}%)", price(summary["iva"])],
        ["Total", price(summary["total"])],
    ], colWidths=[135, 105], hAlign="RIGHT")
    taxes.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#ebe5db")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ]))
    document.build([
        Paragraph("MOTO GARAJE · ACCESORIOS", styles["Heading3"]),
        Paragraph("Vista previa de factura", title),
        Paragraph("Documento de demostración sin validez fiscal. Precios en COP con IVA incluido.", normal),
        Spacer(1, 18), items, Spacer(1, 16), taxes,
    ])
    return output.getvalue()
