# Copyright 2025 Odoo Community Association (OCA)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PajakeIOCancelWizard(models.TransientModel):
    _name = "l10n.id.pajak.io.cancel.wizard"
    _description = "Batalkan Invoice di Pajak.io"

    move_id = fields.Many2one(
        "account.move",
        string="Invoice",
        required=True,
        readonly=True,
    )
    transaction_id = fields.Many2one(
        "l10n.id.pajak.io.transaction",
        string="Transaksi",
        readonly=True,
        compute="_compute_transaction_id",
    )
    no_faktur = fields.Char(
        string="Nomor Faktur",
        related="transaction_id.no_faktur",
        readonly=True,
    )
    transaction_status = fields.Selection(
        related="transaction_id.transaction_status",
        readonly=True,
    )

    @api.depends("move_id", "move_id.pajak_io_transaction_ids")
    def _compute_transaction_id(self):
        for rec in self:
            rec.transaction_id = rec.move_id.pajak_io_transaction_ids[:1]

    def action_cancel(self):
        self.ensure_one()
        tx = self.transaction_id
        if not tx or not tx.transaction_id:
            raise UserError(_("Tidak ada transaksi Pajak.io aktif pada invoice ini."))

        if tx.transaction_status != "APPROVAL_SUKSES":
            raise UserError(
                _(
                    "Hanya faktur dengan status APPROVAL_SUKSES yang dapat dibatalkan. "
                    "Status saat ini: %(status)s.",
                    status=tx.transaction_status,
                )
            )

        config = self.move_id.company_id.get_pajak_io_config()
        service = config.get_service()
        data = service.cancel_vat_output(tx.transaction_id)

        update_vals = {
            "response_payload": json.dumps(data, indent=2),
            "last_checked_at": fields.Datetime.now(),
        }
        if data.get("statusTransaksi"):
            update_vals["transaction_status"] = data["statusTransaksi"]
        if data.get("statusFaktur"):
            update_vals["invoice_status"] = data["statusFaktur"]
        elif not data.get("statusFaktur"):
            # If buyer has credited the invoice, API returns waiting status
            update_vals["invoice_status"] = "MENUNGGU_PEMBATALAN"
        if data.get("pdfUrl"):
            update_vals["pdf_url"] = data["pdfUrl"]

        tx.write(update_vals)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Pembatalan Diproses"),
                "message": _(
                    "Status faktur: %(status)s. "
                    "Jika menunggu persetujuan pembeli, gunakan Refresh Status untuk memperbarui.",
                    status=tx.invoice_status,
                ),
                "type": "warning" if tx.invoice_status == "MENUNGGU_PEMBATALAN" else "success",
                "sticky": tx.invoice_status == "MENUNGGU_PEMBATALAN",
            },
        }
