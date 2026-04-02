# Copyright 2025 Odoo Community Association (OCA)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import _, fields, models
from odoo.exceptions import UserError


class ResCompany(models.Model):
    _inherit = "res.company"

    pajak_io_config_id = fields.Many2one(
        "l10n.id.pajak.io.config",
        string="Konfigurasi Pajak.io",
        domain="[('company_id', '=', id)]",
    )

    def get_pajak_io_config(self):
        self.ensure_one()
        config = self.pajak_io_config_id
        if not config:
            raise UserError(
                _(
                    "Konfigurasi Pajak.io belum diatur untuk perusahaan %(company)s. "
                    "Silakan atur di Accounting → Konfigurasi → Pajak.io.",
                    company=self.name,
                )
            )
        return config
