"""Home/Fashion import workbook, built on request (Ardmore, tickets 0165/0166).

The importer only ever offered a fixed template file whose "Allowed values" sheet was
a copy of the dropdown lists from 29 Sep 2026. This builds the same workbook on demand:

- no category  -> the template (two sample rows) with today's allowed values;
- a category   -> every active Home or Fashion item with its current attributes, so
                  staff can correct them in Excel and upload the sheet back with the
                  importer's Update Only ticked.

Price, cost, quantity and unit columns are always left empty: on an Update Only run a
blank cell is left alone, so the upload changes attributes and nothing else, and it
can never add stock.
"""

from io import BytesIO

import frappe
from frappe.utils import formatdate, nowdate
from openpyxl import load_workbook

TEMPLATE = ("public", "help", "Home_Fashion_Import_Template.xlsx")

# Items-sheet column -> Item field, for the columns that are filled from the item.
ITEM_COLUMNS = {
    "item_code": "item_code",
    "item_name": "item_name",
    "item_group": "item_group",
    "sub_category": "custom_sub_category",
    "collection": "custom_collection",
    "design": "custom_design",
    "colour": "custom_colour",
    "base_cloth": "custom_base_cloth",
    "size": "custom_size",
}

# Allowed-values column -> the Item Select field whose options the importer checks.
ALLOWED_FIELDS = {
    "sub_category": "custom_sub_category",
    "collection": "custom_collection",
    "design": "custom_design",
    "colour": "custom_colour",
    "base_cloth": "custom_base_cloth",
    "size": "custom_size",
}

ALLOWED_HEADER_ROW = 3


@frappe.whitelist()
def download_import_sheet(category=None):
    """Send the Home/Fashion import workbook as an .xlsx download."""
    frappe.has_permission("Home Fashion Importer", "write", throw=True)
    frappe.has_permission("Item", "read", throw=True)

    category = (category or "").strip()
    if category and category not in ("Home", "Fashion"):
        frappe.throw(frappe._("Category must be Home or Fashion."))

    wb = load_workbook(frappe.get_app_path("nest_help", *TEMPLATE))
    items_ws = wb["Items"]
    if category:
        _fill_items(items_ws, category)
    _fill_allowed_values(wb["Allowed values"])
    # The importer reads the active sheet, so the upload must open on Items.
    wb.active = wb.worksheets.index(items_ws)

    out = BytesIO()
    wb.save(out)

    stamp = nowdate()
    if category:
        filename = f"Home_Fashion_{category}_Current_Items_{stamp}.xlsx"
    else:
        filename = "Home_Fashion_Import_Template.xlsx"
    frappe.response["filename"] = filename
    frappe.response["filecontent"] = out.getvalue()
    frappe.response["type"] = "binary"


def _fill_items(ws, category):
    """Replace the sample rows with every active item of this category."""
    headers = [str(c.value or "").strip() for c in ws[1]]
    ws.delete_rows(2, ws.max_row)

    # get_list, not get_all: the download shows only items this user may read.
    rows = frappe.get_list(
        "Item",
        filters={"custom_category": category, "disabled": 0},
        fields=list(ITEM_COLUMNS.values()),
        order_by="item_code asc",
        limit_page_length=0,
    )
    for r_idx, row in enumerate(rows, start=2):
        for c_idx, header in enumerate(headers, start=1):
            field = ITEM_COLUMNS.get(header)
            value = row.get(field) if field else None
            if value not in (None, ""):
                ws.cell(row=r_idx, column=c_idx, value=str(value))


def _fill_allowed_values(ws):
    """Rewrite the allowed-values columns from the dropdown lists as they are now."""
    ws["A1"] = (
        "Values the import accepts, as at "
        + formatdate(nowdate(), "d MMMM yyyy")
        + ". Spelling must match; capitals and spaces do not matter. A value that is not "
        "listed is rejected for that field. Add a new value to its list in ERPNext BEFORE importing."
    )
    for col in range(1, ws.max_column + 1):
        header = str(ws.cell(row=ALLOWED_HEADER_ROW, column=col).value or "").strip()
        field = ALLOWED_FIELDS.get(header)
        if not field:
            continue  # uom keeps the template's own list (Each, Meter)
        for r in range(ALLOWED_HEADER_ROW + 1, ws.max_row + 1):
            # .value = None, not cell(value=None): openpyxl ignores a None passed to cell().
            ws.cell(row=r, column=col).value = None
        for r, option in enumerate(_options(field), start=ALLOWED_HEADER_ROW + 1):
            ws.cell(row=r, column=col, value=option)


def _options(fieldname):
    """The Select options the importer checks against (same source as the importer)."""
    opts = frappe.db.get_value("Custom Field", {"dt": "Item", "fieldname": fieldname}, "options") or ""
    return [o.strip() for o in opts.split("\n") if o.strip()]
