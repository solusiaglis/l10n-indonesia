# Copyright 2025 Odoo Community Association (OCA)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
{
    "name": "Indonesian Tax E-Invoice (Pajak.io)",
    "version": "18.0.1.0.0",
    "author": "Odoo Community Association (OCA)",
    "summary": "Submit and manage Faktur Pajak Keluaran via Pajak.io API",
    "license": "AGPL-3",
    "category": "Accounting/Localizations",
    "website": "https://github.com/OCA/l10n-indonesia",
    "depends": [
        "account",
        "l10n_id_efaktur_coretax",
    ],
    "data": [
        "security/pajak_io_security.xml",
        "security/ir.model.access.csv",
        "views/pajak_io_config_views.xml",
        "views/pajak_io_transaction_views.xml",
        "views/res_partner_views.xml",
        "views/account_move_views.xml",
        "views/pajak_io_submit_wizard_views.xml",
        "views/pajak_io_cancel_wizard_views.xml",
        "views/pajak_io_test_connection_views.xml",
    ],
    "external_dependencies": {"python": ["requests"]},
    "installable": True,
    "application": False,
    "development_status": "Beta",
    "maintainers": ["OCA"],
}
