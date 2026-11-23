"""Big Home/Fashion import sheets run in the background (Ardmore, ticket 0165).

The importer's own Server Script ("Home Fashion Importer - Import", Before Save) does
the work inside the Save request. A sheet of more than 300 rows would run past the
request time limit, so for such a sheet the Server Script checks everything it can
up front (columns, price lists, warehouse), imports nothing, and sets
doc.flags.nest_hfi_queued. After that save commits, one background job here saves the
importer again with doc.flags.nest_hfi_background set, and the Server Script then
imports every row exactly as it would have in the foreground.

The job runs as the user who clicked Save (frappe.enqueue carries the session user),
so the import has that user's permissions, and they get a bell notification when it
is done or has failed.
"""

import frappe
from frappe.utils import strip_html

DOCTYPE = "Home Fashion Importer"


def queue_big_import(doc, method=None):
    """on_update: hand a sheet the Server Script marked as queued to a background job."""
    if not doc.flags.get("nest_hfi_queued"):
        return
    frappe.enqueue(
        "nest_help.home_fashion_import.run_import",
        queue="long",
        timeout=3600,
        job_id=f"nest_hfi::{doc.name}",
        deduplicate=True,
        enqueue_after_commit=True,
        name=doc.name,
    )


def run_import(name):
    """Background job: import every row of a queued sheet, then tell the user."""
    doc = frappe.get_doc(DOCTYPE, name)
    if doc.imported:
        return

    doc.flags.nest_hfi_background = True
    try:
        doc.save()
        frappe.db.commit()
    except Exception as e:  # noqa: BLE001 - any failure must reach the user, not die in the worker
        # The whole import is one transaction, so a failure leaves every item as it was.
        frappe.db.rollback()
        frappe.log_error(title=f"Home Fashion import {name} failed")
        reason = strip_html(str(e)).strip()[:500] or e.__class__.__name__
        frappe.db.set_value(
            DOCTYPE,
            name,
            "import_log",
            "FAILED: nothing was changed.\n\nReason: "
            + reason
            + "\n\nCorrect the sheet if the reason points at it, then make a new Home Fashion "
            "Importer and attach the sheet again.",
            update_modified=False,
        )
        notify(name, f"Import {name} failed. Nothing was changed. Open it for the reason.")
        return

    summary = (doc.import_log or "").split("\n", 1)[0]
    notify(name, f"Import {name} is done. {summary}")


def notify(name, subject):
    """Bell notification for the user who started the import. Never fails the job:
    the import itself is already committed (or rolled back) by now."""
    try:
        # ignore_permissions: users may not create Notification Logs themselves, even for
        # their own bell; this one is addressed only to the user running the job.
        frappe.get_doc(
            {
                "doctype": "Notification Log",
                "for_user": frappe.session.user,
                "type": "Alert",
                "document_type": DOCTYPE,
                "document_name": name,
                "subject": subject,
            }
        ).insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception:  # noqa: BLE001 - a missing bell must not mark a finished import as failed
        frappe.db.rollback()
        frappe.log_error(title=f"Home Fashion import {name}: notification failed")
