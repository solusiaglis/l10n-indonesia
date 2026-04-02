# Copyright 2025 Odoo Community Association (OCA)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .pajak_io_service import IDENTITY_TYPE_MAP, KODE_TRANSAKSI_MAP


class AccountMove(models.Model):
    _inherit = "account.move"

    # ── Pajak.io transaction history ────────────────────────────────────
    pajak_io_transaction_ids = fields.One2many(
        "l10n.id.pajak.io.transaction",
        "move_id",
        string="Pajak.io Transactions",
        copy=False,
    )

    # ── Computed summary from latest transaction ────────────────────────
    pajak_io_status = fields.Selection(
        [
            ("not_submitted", "Belum Disubmit"),
            ("submitted", "Submitted"),
            ("approved", "Disetujui"),
            ("rejected", "Ditolak"),
            ("cancelled", "Dibatalkan"),
            ("waiting_cancellation", "Menunggu Pembatalan"),
            ("waiting_replacement", "Menunggu Pengganti"),
        ],
        string="Status Pajak.io",
        compute="_compute_pajak_io_status",
        store=True,
        copy=False,
    )
    pajak_io_transaction_id = fields.Char(
        string="Transaction ID",
        compute="_compute_pajak_io_status",
        store=True,
        copy=False,
    )
    pajak_io_no_faktur = fields.Char(
        string="Nomor Faktur Pajak",
        compute="_compute_pajak_io_status",
        store=True,
        copy=False,
    )

    # ── Additional fields for Pajak.io submission ───────────────────────
    # Note: l10n_id_kode_transaksi already exists from l10n_id_efaktur
    # Note: l10n_id_coretax_add_info_07/_08 from l10n_id_efaktur_coretax
    # Note: l10n_id_coretax_custom_doc from l10n_id_efaktur_coretax
    # Note: l10n_id_replace_invoice_id from l10n_id_efaktur

    l10n_id_termin_pembayaran = fields.Selection(
        [
            ("NORMAL", "Normal"),
            ("UANG_MUKA", "Uang Muka (Down Payment)"),
            ("PELUNASAN", "Pelunasan (Final Payment)"),
        ],
        string="Termin Pembayaran",
        default="NORMAL",
        copy=True,
    )

    # ── Computed status ─────────────────────────────────────────────────

    @api.depends(
        "pajak_io_transaction_ids.transaction_status",
        "pajak_io_transaction_ids.invoice_status",
        "pajak_io_transaction_ids.transaction_id",
        "pajak_io_transaction_ids.no_faktur",
    )
    def _compute_pajak_io_status(self):
        for move in self:
            latest = move.pajak_io_transaction_ids[:1]
            move.pajak_io_transaction_id = latest.transaction_id
            move.pajak_io_no_faktur = latest.no_faktur
            inv_status = latest.invoice_status
            tx_status = latest.transaction_status

            if not latest:
                move.pajak_io_status = "not_submitted"
            elif inv_status == "BATAL":
                move.pajak_io_status = "cancelled"
            elif inv_status == "MENUNGGU_PEMBATALAN":
                move.pajak_io_status = "waiting_cancellation"
            elif inv_status in ("MENUNGGU_PENGGANTI", "DIGANTI"):
                move.pajak_io_status = "waiting_replacement"
            elif tx_status == "APPROVAL_SUKSES":
                move.pajak_io_status = "approved"
            elif tx_status == "DITOLAK":
                move.pajak_io_status = "rejected"
            elif tx_status in (
                "DRAFT",
                "SEDANG_DIKIRIM",
                "MENUNGGU_VERIFIKASI_DJP",
            ):
                move.pajak_io_status = "submitted"
            else:
                move.pajak_io_status = "not_submitted"

    # ── Actions ─────────────────────────────────────────────────────────

    def action_pajak_io_submit(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Submit ke Pajak.io"),
            "res_model": "l10n.id.pajak.io.submit.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_move_id": self.id},
        }

    def action_pajak_io_cancel(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Batalkan di Pajak.io"),
            "res_model": "l10n.id.pajak.io.cancel.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_move_id": self.id},
        }

    def action_pajak_io_refresh_status(self):
        self.ensure_one()
        tx = self.pajak_io_transaction_ids[:1]
        if not tx or not tx.transaction_id:
            raise UserError(_("Tidak ada transaksi Pajak.io yang aktif."))
        config = self.company_id.get_pajak_io_config()
        service = config.get_service()
        data = service.get_detail(tx.transaction_id)
        tx.write(
            {
                "transaction_status": data.get("statusTransaksi") or data.get("transactionStatus"),
                "invoice_status": data.get("statusFaktur") or data.get("invoiceStatus"),
                "pdf_url": data.get("pdfUrl") or data.get("urlPdf"),
                "response_payload": json.dumps(data, indent=2),
                "last_checked_at": fields.Datetime.now(),
            }
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Status Diperbarui"),
                "message": _(
                    "Status transaksi: %(tx)s | Status faktur: %(inv)s",
                    tx=tx.transaction_status,
                    inv=tx.invoice_status,
                ),
                "type": "success",
            },
        }

    def action_pajak_io_download_pdf(self):
        self.ensure_one()
        tx = self.pajak_io_transaction_ids[:1]
        if not tx or not tx.transaction_id:
            raise UserError(_("Tidak ada transaksi Pajak.io yang aktif."))
        config = self.company_id.get_pajak_io_config()
        service = config.get_service()
        pdf_b64 = service.get_pdf(tx.transaction_id)
        if not pdf_b64:
            raise UserError(_("PDF tidak tersedia untuk transaksi ini."))
        filename = f"faktur_{tx.no_faktur or tx.transaction_id}.pdf"
        attachment = self.env["ir.attachment"].create(
            {
                "name": filename,
                "type": "binary",
                "datas": pdf_b64,
                "res_model": self._name,
                "res_id": self.id,
                "mimetype": "application/pdf",
            }
        )
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "new",
        }

    # ── Payload builder (used by submit wizard) ─────────────────────────

    def _pajak_io_prepare_payload(self, is_replacement=False, replaced_no_faktur=""):
        self.ensure_one()
        config = self.company_id.get_pajak_io_config()
        partner = self.partner_id

        kode = self.l10n_id_kode_transaksi or "01"
        kd_jenis = KODE_TRANSAKSI_MAP.get(kode, "TD.00301")

        # keteranganTambahan — required for type 07/08
        keterangan_tambahan = None
        if kode == "07" and hasattr(self, "l10n_id_coretax_add_info_07"):
            kd_tambahan = self.l10n_id_coretax_add_info_07
            custom_doc = getattr(self, "l10n_id_coretax_custom_doc", "")
            if kd_tambahan:
                keterangan_tambahan = {
                    "kode": kd_tambahan,
                    "nomorDokumenPendukung": custom_doc or "",
                }
        elif kode == "08" and hasattr(self, "l10n_id_coretax_add_info_08"):
            kd_tambahan = self.l10n_id_coretax_add_info_08
            custom_doc = getattr(self, "l10n_id_coretax_custom_doc", "")
            if kd_tambahan:
                keterangan_tambahan = {
                    "kode": kd_tambahan,
                    "nomorDokumenPendukung": custom_doc or "",
                }

        invoice_date = self.invoice_date or fields.Date.today()
        masa_pajak = invoice_date.strftime("%m")
        tahun_pajak = invoice_date.strftime("%Y")

        # Buyer identity
        identity_type = self._pajak_io_get_identity_type(partner)
        identity_value = self._pajak_io_get_identity_value(partner)
        nitku = getattr(partner, "l10n_id_nitku", "") or "0000000000000000000000"

        # Payment terms
        termin = self.l10n_id_termin_pembayaran or "NORMAL"
        termin_obj = {"type": termin, "dpp": 0.0, "ppn": 0.0, "ppnbm": 0.0, "nofa": ""}

        # Line items
        barang_jasa = self._pajak_io_prepare_lines()
        total_dpp = sum(ln.get("dpp", 0) for ln in barang_jasa)
        total_dpp_lain = sum(ln.get("dppLain", 0) for ln in barang_jasa)
        total_ppn = sum(ln.get("ppn", 0) for ln in barang_jasa)
        total_ppnbm = sum(ln.get("ppnbm", 0) for ln in barang_jasa)

        payload = {
            "autoUploadDjp": config.auto_upload_djp,
            "pengganti": is_replacement,
            "nofaDiganti": replaced_no_faktur or "",
            "kdJenisTransaksi": kd_jenis,
            "masaPajak": masa_pajak,
            "tahunPajak": tahun_pajak,
            "tanggalFaktur": invoice_date.strftime("%Y-%m-%d"),
            "noInvoice": self.name,
            "barangJasa": barang_jasa,
            "lawanTransaksi": {
                "identityType": identity_type,
                "identityValue": identity_value,
                "nitku": nitku,
                "nama": partner.name or "",
                "telp": partner.phone or "",
                "alamatJalan": partner.street or "",
                "kota": partner.city or "",
                "kodeNegara": partner.country_id.code or "IDN",
                "email": partner.email or "",
            },
            "terminPembayaran": termin_obj,
            "totalDpp": str(total_dpp),
            "totalDppLain": str(total_dpp_lain),
            "totalPpn": str(total_ppn),
            "totalPpnBm": str(total_ppnbm),
        }
        if keterangan_tambahan:
            payload["keteranganTambahan"] = keterangan_tambahan

        return payload

    def _pajak_io_get_identity_type(self, partner):
        doc_type = getattr(partner, "l10n_id_buyer_document_type", "TIN") or "TIN"
        return IDENTITY_TYPE_MAP.get(doc_type, "NPWP")

    def _pajak_io_get_identity_value(self, partner):
        doc_number = getattr(partner, "l10n_id_buyer_document_number", "") or ""
        if doc_number:
            return doc_number
        # Fallback: use partner VAT (NPWP stored in vat field)
        return (partner.vat or "").replace(".", "").replace("-", "")

    def _pajak_io_prepare_lines(self):
        lines = []
        for line in self.invoice_line_ids.filtered(
            lambda l: l.display_type not in ("line_section", "line_note")
        ):
            price_subtotal = line.price_subtotal
            discount_amount = line.price_unit * line.quantity - price_subtotal
            tax_rate = 0.0
            tax_amount = 0.0
            for tax in line.tax_ids:
                if tax.amount_type == "percent":
                    tax_rate = tax.amount
                    tax_amount = price_subtotal * tax_rate / 100
                    break

            dpp = price_subtotal
            lines.append(
                {
                    "jenis": "JASA",
                    "kode": "",
                    "nama": line.name or line.product_id.name or "",
                    "jumlah": int(line.quantity),
                    "kodeSatuan": "UN",
                    "harga": line.price_unit,
                    "totalHarga": line.price_unit * line.quantity,
                    "diskon": discount_amount,
                    "tarifPpn": tax_rate,
                    "dpp": dpp,
                    "cekDppLain": False,
                    "dppLain": 0.0,
                    "ppn": tax_amount,
                    "tarifPpnbm": 0.0,
                    "ppnbm": 0.0,
                }
            )
        return lines
