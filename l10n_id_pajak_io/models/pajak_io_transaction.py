# Copyright 2025 Odoo Community Association (OCA)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import fields, models


class PajakeIOTransaction(models.Model):
    _name = "l10n.id.pajak.io.transaction"
    _description = "Pajak.io Transaction"
    _order = "id desc"

    move_id = fields.Many2one(
        "account.move",
        string="Invoice",
        required=True,
        ondelete="cascade",
        index=True,
        copy=False,
    )
    company_id = fields.Many2one(
        "res.company",
        related="move_id.company_id",
        store=True,
        index=True,
    )

    # ── Pajak.io response identifiers ──────────────────────────────────
    transaction_id = fields.Char(
        string="Transaction ID",
        copy=False,
        readonly=True,
        help="Unique transaction identifier returned by Pajak.io.",
    )
    no_faktur = fields.Char(
        string="Nomor Faktur Pajak",
        copy=False,
        readonly=True,
        help="DGT-assigned tax invoice number.",
    )
    no_invoice = fields.Char(
        string="Nomor Invoice Komersial",
        copy=False,
        readonly=True,
        help="Commercial invoice number sent to Pajak.io.",
    )

    # ── Status ─────────────────────────────────────────────────────────
    transaction_status = fields.Selection(
        [
            ("DRAFT", "Draft"),
            ("SEDANG_DIKIRIM", "Sedang Dikirim"),
            ("MENUNGGU_VERIFIKASI_DJP", "Menunggu Verifikasi DJP"),
            ("APPROVAL_SUKSES", "Approval Sukses"),
            ("DITOLAK", "Ditolak"),
            ("FAILED", "Failed"),
        ],
        string="Transaction Status",
        copy=False,
        readonly=True,
    )
    invoice_status = fields.Selection(
        [
            ("NORMAL", "Normal"),
            ("NORMAL_PENGGANTI", "Normal Pengganti"),
            ("DIGANTI", "Diganti"),
            ("BATAL", "Batal"),
            ("MENUNGGU_PENGGANTI", "Menunggu Pengganti"),
            ("MENUNGGU_PEMBATALAN", "Menunggu Pembatalan"),
        ],
        string="Invoice Status",
        copy=False,
        readonly=True,
    )

    # ── Replacement info ───────────────────────────────────────────────
    is_replacement = fields.Boolean(
        string="Is Replacement (Pengganti)",
        default=False,
        copy=False,
        readonly=True,
    )
    replaced_no_faktur = fields.Char(
        string="Nomor Faktur Diganti",
        copy=False,
        readonly=True,
        help="nofaDiganti — the invoice number this transaction replaces.",
    )

    # ── PDF ────────────────────────────────────────────────────────────
    pdf_url = fields.Char(
        string="PDF Link",
        copy=False,
        readonly=True,
    )

    # ── Request / Response logs ────────────────────────────────────────
    request_payload = fields.Text(
        string="Request Payload",
        copy=False,
        readonly=True,
    )
    response_payload = fields.Text(
        string="Response Payload",
        copy=False,
        readonly=True,
    )

    # ── Timestamps ─────────────────────────────────────────────────────
    submitted_at = fields.Datetime(
        string="Submitted At",
        copy=False,
        readonly=True,
    )
    last_checked_at = fields.Datetime(
        string="Last Checked At",
        copy=False,
        readonly=True,
    )
