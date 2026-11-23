app_name = "nest_help"
app_title = "Nest Help"
app_publisher = "NestERP"
app_description = "Contextual help system for the NestERP platform. Drop HTML files in public/help/ and any NestERP app can auto-discover and display help badges."
app_email = "info@nesterp.com"
app_license = "Proprietary"

# Loaded on every desk page — exposes nestHelp.badge() for any app to call
app_include_js = ["/assets/nest_help/js/nest_help.js"]
app_include_css = ["/assets/nest_help/css/nest_help.css"]

# Ardmore Home/Fashion importer: a sheet over 300 rows is imported in a background job.
doc_events = {
    "Home Fashion Importer": {
        "on_update": "nest_help.home_fashion_import.queue_big_import",
    },
}
