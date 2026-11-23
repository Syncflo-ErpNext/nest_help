# nest_help — Claude session notes

Standalone NestERP app: contextual help system for the entire platform.

## How it works

- HTML help pages live in `nest_help/public/help/<slug>.html`
- Served as static assets at `/assets/nest_help/help/<slug>.html`
- `nest_help.js` is loaded on every desk page via `app_include_js`
- Exposes `window.nestHelp` with `.discover()`, `.badge()`, `.open()`, `.slug()`
- Any NestERP app adds `data-help="<slug>"` to elements and calls
  `nestHelp.discover($container)` — the badge auto-appears if the file exists
- No database, no admin config, no doctype — just HTML files in the repo

## Slug convention

Tile label "Sales Persons" -> slug `sales-persons` -> file `public/help/sales-persons.html`

`nestHelp.slug('Open POS')` returns `open-pos`.

## Adding a help page

1. Create `public/help/<slug>.html` (copy an existing page as template)
2. Push + deploy
3. The `?` badge appears automatically on any element with `data-help="<slug>"`

## Repo

- GitHub: `Syncflo-design/nest_help` (org for NestERP apps)
- Module: `Nest Help`

## Ardmore Home/Fashion importer (0.0.13, 0.0.14)

- `api.download_import_sheet`: Download Template / Download Current Items (tickets 0165/0166).
- `home_fashion_import.py` (0.0.14): a sheet over 300 rows is imported in a background job.
  The site's Server Script "Home Fashion Importer - Import" imports nothing for such a sheet
  and sets `doc.flags.nest_hfi_queued`; the `on_update` hook enqueues `run_import`, which saves
  the importer again with `doc.flags.nest_hfi_background` so the Server Script imports every
  row, then sends the user a bell notification. The Server Script copy (and the rollback
  copy) live in `CoWork_Helper/sites/ardmore-item-attributes-2026-11-23/`.
- Order matters: deploy the app first, then update the Server Script. A Server Script that
  queues without the app installed would leave big sheets queued forever.
- 0.0.15 (23 Nov 2026): `download_import_sheet(category, in_stock=0)`. in_stock=1 keeps only items
  with stock (Bin actual_qty > 0 in the user's default company's warehouses). Every row that looks
  wrong is yellow with the reason in a last `check` column (the importer ignores unknown columns):
  a value the item name contradicts (one list value in the name, a different one on the item;
  design read first and taken out of the name, collection read from the whole name), or the list's
  first value (Bonnie/Acacia/Amber/Acrylic/Small = what ERPNext gave items created without one).
  The Client Script "Home Fashion Importer - Download Template" asks All items / Only items with
  stock; update it on the site only AFTER this version is deployed (the old api has no in_stock).
  Help page import-home-fashion.html updated to match.
