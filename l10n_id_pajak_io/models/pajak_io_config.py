# Copyright 2025 Odoo Community Association (OCA)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .pajak_io_service import PajakeIOService


class PajakeIOConfig(models.Model):
    _name = "l10n.id.pajak.io.config"
    _description = "Pajak.io Configuration"

    name = fields.Char(required=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    api_key = fields.Char(
        string="API Key",
        required=True,
        help="Raw token obtained from Pajak.io support. Will be Base64-encoded before use.",
    )
    environment = fields.Selection(
        [("sandbox", "Sandbox"), ("production", "Production")],
        required=True,
        default="sandbox",
    )
    auto_upload_djp = fields.Boolean(
        string="Auto Upload to DJP",
        default=False,
        help="Automatically upload to DGT (DJP) after draft creation succeeds.",
    )
    request_timeout = fields.Integer(
        string="Request Timeout (s)",
        default=30,
    )
    logging_enabled = fields.Boolean(
        string="Enable Request Logging",
        default=False,
        help="Log raw JSON request and response payloads on each transaction.",
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "company_uniq",
            "unique(company_id)",
            "Only one Pajak.io configuration is allowed per company.",
        )
    ]

    def get_service(self):
        self.ensure_one()
        return PajakeIOService(self)

    def action_test_connection(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Test Pajak.io Connection"),
            "res_model": "l10n.id.pajak.io.test.connection",
            "view_mode": "form",
            "target": "new",
            "context": {"default_config_id": self.id},
        }

    @api.constrains("request_timeout")
    def _check_timeout(self):
        for rec in self:
            if rec.request_timeout <= 0:
                raise UserError(_("Request timeout must be greater than 0."))
