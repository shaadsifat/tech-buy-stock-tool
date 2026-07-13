import io
from datetime import datetime

from openpyxl import Workbook

from app import models

HEADERS = ["Category", "Product Name", "Tech Buy Link", "Other website link"]


def build_workbook():
    rows = models.get_all_products_with_category()

    wb = Workbook()
    ws = wb.active
    ws.title = "Products"

    ws.append(HEADERS)
    for cell in ws[1]:
        cell.font = cell.font.copy(bold=True)

    for row in rows:
        ws.append([row["category"], row["name"], row["techbuy_link"], row["other_link"]])

    widths = [18, 34, 42, 42]
    for i, width in enumerate(widths, start=1):
        ws.column_dimensions[chr(64 + i)].width = width

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def build_filename():
    now = datetime.now()
    return f"Tech_Buy_Products_{now.strftime('%d%b_%Y_%I%M%p').lower()}.xlsx"
