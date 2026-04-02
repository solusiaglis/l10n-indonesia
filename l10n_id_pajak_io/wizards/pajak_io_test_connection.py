# Copyright 2025 Odoo Community Association (OCA)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import _, api, fields, models


class PajakeIOTestConnection(models.TransientModel):
    _name = "l10n.id.pajak.io.test.connection"
    _description = "Test Koneksi Pajak.io"

    config_id = fields.Many2one(
        "l10n.id.pajak.io.config",
        string="Konfigurasi",
        required=True,
    )
    status = fields.Selection(
        [("success", "Berhasil"), ("error", "Gagal")],
        string="Status",
        readonly=True,
    )
    message = fields.Text(string="Pesan", readonly=True)

    @api.model
    def default_get(self, field_names):
        res = super().default_get(field_names)
        config_id = self.env.context.get("default_config_id")
        if config_id:
            res["config_id"] = config_id
        return res

    def action_test(self):
        self.ensure_one()
        config = self.config_id
        service = config.get_service()
        try:
            # Use the list endpoint as a lightweight connectivity check
            service._call(
                "POST",
                "/efaktur/v3/penjualan/list",
                {"page": 1, "size": 1, "sortBy": "createdAt", "sortOrder": "ASC"},
            )
            self.write(
                {
                    "status": "success",
                    "message": _("Koneksi ke Pajak.io berhasil. Environment: %s")
                    % config.environment.upper(),
                }
            )
        except Exception as exc:
            self.write({"status": "error", "message": str(exc)})

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
