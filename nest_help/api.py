"""Home/Fashion import workbook, built on request (Ardmore, tickets 0165/0166).

The importer only ever offered a fixed template file whose "Allowed values" sheet was
a copy of the dropdown lists from 29 Sep 2026. This builds the same workbook on demand:

- no category  -> the template (two sample rows) with today's allowed values;
- a category   -> every active Home or Fashion item with its current attributes, so
                  staff can correct them in Excel and upload the sheet back with the
                  importer's Update Only ticked. in_stock=1 keeps only items with stock.
                  Rows that look wrong are coloured yellow with the reason in a last
                  "check" column (the importer ignores columns it does not know).

Price, cost, quantity and unit columns are always left empty: on an Update Only run a
blank cell is left alone, so the upload changes attributes and nothing else, and it
can never add stock.
"""

import re
from io import BytesIO

import frappe
from frappe.utils import cint, formatdate, nowdate
from openpyxl import load_workbook
from openpyxl.styles import PatternFill

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

# The attribute columns a row is checked on, with the label used in the "check" reason.
# Design is read first and taken out of the name, so "Monkey Natural" never also gives
# the colour Natural.
CHECK_COLUMNS = {
    "design": "Design",
    "collection": "Collection",
    "colour": "Colour",
    "base_cloth": "Base Cloth",
    "size": "Size",
}
YELLOW = PatternFill("solid", fgColor="FFF59D")


@frappe.whitelist()
def download_import_sheet(category=None, in_stock=0):
    """Send the Home/Fashion import workbook as an .xlsx download."""
    frappe.has_permission("Home Fashion Importer", "write", throw=True)
    frappe.has_permission("Item", "read", throw=True)

    category = (category or "").strip()
    if category and category not in ("Home", "Fashion"):
        frappe.throw(frappe._("Category must be Home or Fashion."))

    wb = load_workbook(frappe.get_app_path("nest_help", *TEMPLATE))
    items_ws = wb["Items"]
    if category:
        _fill_items(items_ws, category, cint(in_stock))
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


def _fill_items(ws, category, in_stock=0):
    """Replace the sample rows with the active items of this category, marking the ones to check."""
    headers = [str(c.value or "").strip() for c in ws[1]]
    ws.delete_rows(2, ws.max_row)
    check_col = len(headers) + 1
    ws.cell(row=1, column=check_col, value="check")

    filters = {"custom_category": category, "disabled": 0}
    if in_stock:
        # Stock in the user's own company (Ardmore), not the training company. get_all: only
        # item codes are read here; the items themselves still go through get_list below.
        bin_filters = {"actual_qty": [">", 0]}
        company = frappe.defaults.get_user_default("Company")
        if company:
            bin_filters["warehouse"] = [
                "in",
                frappe.get_all("Warehouse", filters={"company": company}, pluck="name"),
            ]
        filters["name"] = ["in", frappe.get_all("Bin", filters=bin_filters, pluck="item_code", distinct=True)]
    # get_list, not get_all: the download shows only items this user may read.
    rows = frappe.get_list(
        "Item",
        filters=filters,
        fields=list(ITEM_COLUMNS.values()),
        order_by="item_code asc",
        limit_page_length=0,
    )
    lists = {key: _options(ITEM_COLUMNS[key]) for key in CHECK_COLUMNS}
    for r_idx, row in enumerate(rows, start=2):
        for c_idx, header in enumerate(headers, start=1):
            field = ITEM_COLUMNS.get(header)
            value = row.get(field) if field else None
            if value not in (None, ""):
                ws.cell(row=r_idx, column=c_idx, value=str(value))
        problems = _row_problems(row, lists)
        if problems:
            ws.cell(row=r_idx, column=check_col, value="; ".join(problems))
            for c_idx in range(1, check_col + 1):
                ws.cell(row=r_idx, column=c_idx).fill = YELLOW


def _norm(text):
    """Lower case, words only, sizes written 60x60, padded so a match is a whole word."""
    text = re.sub(r"(\d)\s*x\s*(\d)", r"\1x\2", str(text or "").lower())
    return " " + re.sub(r"[^a-z0-9/&]+", " ", text).strip() + " "


def _row_problems(row, lists):
    """Why this row looks wrong: a value the item name contradicts, or the list's first value."""
    full = name = _norm(row.get("item_name"))
    problems, automatic = [], []
    for key, label in CHECK_COLUMNS.items():
        options = lists[key]
        current = str(row.get(ITEM_COLUMNS[key]) or "")
        # Collection is read from the whole name: "Wonderboy Wisdom" is a design of Wonderboy.
        found, rest = [], (full if key == "collection" else name)
        for option in sorted(options, key=len, reverse=True):
            if _norm(option) in rest:
                found.append(option)
                rest = rest.replace(_norm(option), " | ")
        if key == "design" and len(found) == 1:
            name = rest
        # One value in the name, a different one on the item, and neither part of the other
        # (Royal / Royal Red is left alone).
        if (
            len(found) == 1
            and found[0] != current
            and (
                not current
                or (_norm(current) not in _norm(found[0]) and _norm(found[0]) not in _norm(current))
            )
        ):
            problems.append(f"Name says {found[0]}, {label} says {current or 'nothing'}")
        elif options and current == options[0]:
            automatic.append(f"{label} {current}")
    if automatic:
        # A list's first value is what ERPNext gave items created without one.
        problems.append(", ".join(automatic) + " probably filled in automatically")
    return problems


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
