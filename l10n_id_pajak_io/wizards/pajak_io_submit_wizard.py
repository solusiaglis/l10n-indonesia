# Copyright 2025 Odoo Community Association (OCA)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PajakeIOSubmitWizard(models.TransientModel):
    _name = "l10n.id.pajak.io.submit.wizard"
    _description = "Submit Invoice ke Pajak.io"

    move_id = fields.Many2one(
        "account.move",
        string="Invoice",
        required=True,
        readonly=True,
    )
    is_replacement = fields.Boolean(
        string="Faktur Pengganti",
        default=False,
        help="Centang jika ini adalah faktur pengganti (pengganti).",
    )
    replaced_transaction_id = fields.Many2one(
        "l10n.id.pajak.io.transaction",
        string="Faktur yang Diganti",
        domain="[('move_id.move_type', '=', 'out_invoice'), "
        "('invoice_status', 'in', ['NORMAL', 'NORMAL_PENGGANTI', 'APPROVAL_SUKSES'])]",
        help="Pilih transaksi Pajak.io dari faktur yang akan digantikan.",
    )
    replaced_no_faktur = fields.Char(
        string="Nomor Faktur Diganti",
        related="replaced_transaction_id.no_faktur",
        readonly=True,
    )

    # Display info
    kode_transaksi = fields.Selection(
        related="move_id.l10n_id_kode_transaksi",
        readonly=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        related="move_id.partner_id",
        readonly=True,
    )

    @api.onchange("is_replacement")
    def _onchange_is_replacement(self):
        if not self.is_replacement:
            self.replaced_transaction_id = False

    @api.constrains("is_replacement", "replaced_transaction_id")
    def _check_replacement(self):
        for rec in self:
            if rec.is_replacement and not rec.replaced_transaction_id:
                raise UserError(
                    _("Faktur pengganti harus memilih transaksi yang akan diganti.")
                )
            if rec.is_replacement and not rec.replaced_no_faktur:
                raise UserError(
                    _(
                        "Transaksi yang dipilih tidak memiliki Nomor Faktur Pajak. "
                        "Pastikan faktur asal sudah berhasil disubmit ke Pajak.io."
                    )
                )

    def action_submit(self):
        self.ensure_one()
        move = self.move_id
        if move.state != "posted":
            raise UserError(_("Hanya invoice yang sudah dikonfirmasi (Posted) yang dapat disubmit."))

        config = move.company_id.get_pajak_io_config()
        service = config.get_service()

        replaced_no_faktur = ""
        if self.is_replacement:
            replaced_no_faktur = self.replaced_no_faktur or ""

        payload = move._pajak_io_prepare_payload(
            is_replacement=self.is_replacement,
            replaced_no_faktur=replaced_no_faktur,
        )

        data = service.create_vat_output(payload)

        transaction_id = data.get("transactionId") or data.get("transaction_id", "")
        no_invoice = data.get("noInvoice") or data.get("no_invoice", move.name)

        tx_vals = {
            "move_id": move.id,
            "transaction_id": transaction_id,
            "no_invoice": no_invoice,
            "is_replacement": self.is_replacement,
            "replaced_no_faktur": replaced_no_faktur,
            "transaction_status": "DRAFT",
            "invoice_status": "NORMAL_PENGGANTI" if self.is_replacement else "NORMAL",
            "request_payload": json.dumps(payload, indent=2),
            "response_payload": json.dumps(data, indent=2),
            "submitted_at": fields.Datetime.now(),
        }
        # Populate fields from response if available
        if data.get("nomorFaktur"):
            tx_vals["no_faktur"] = data["nomorFaktur"]
        if data.get("statusTransaksi"):
            tx_vals["transaction_status"] = data["statusTransaksi"]
        if data.get("statusFaktur"):
            tx_vals["invoice_status"] = data["statusFaktur"]
        if data.get("pdfUrl"):
            tx_vals["pdf_url"] = data["pdfUrl"]

        self.env["l10n.id.pajak.io.transaction"].create(tx_vals)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Berhasil Disubmit"),
                "message": _(
                    "Invoice berhasil dikirim ke Pajak.io. Transaction ID: %(txid)s",
                    txid=transaction_id,
                ),
                "type": "success",
                "sticky": False,
            },
        }
