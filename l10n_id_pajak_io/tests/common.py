# Copyright 2025 Odoo Community Association (OCA)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase

_SERVICE_PATH = "odoo.addons.l10n_id_pajak_io.models.pajak_io_service.PajakeIOService"
_REQUESTS_PATH = (
    "odoo.addons.l10n_id_pajak_io.models.pajak_io_service.requests.request"
)


class TestPajakIoCommon(TransactionCase):
    """Base class for Pajak.io integration tests.

    Provides:
    - A Pajak.io config record linked to the test company
    - A customer partner with Indonesian tax fields
    - A posted customer invoice ready for submission
    - Mock helpers to intercept HTTP calls without network access
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        # --- Pajak.io configuration ---
        cls.pajak_config = cls.env["l10n.id.pajak.io.config"].create(
            {
                "name": "Test Pajak.io Sandbox",
                "company_id": cls.company.id,
                "api_key": "test-api-key-sandbox-00000000",
                "environment": "sandbox",
                "auto_upload_djp": False,
                "request_timeout": 10,
                "logging_enabled": False,
            }
        )
        cls.company.pajak_io_config_id = cls.pajak_config.id

        # --- Partner with Indonesian identity fields ---
        cls.customer = cls.env["res.partner"].create(
            {
                "name": "PT. Demo Customer Indonesia",
                "vat": "123456789012345",
                "l10n_id_buyer_document_type": "TIN",
                "l10n_id_buyer_document_number": "123456789012345",
                "l10n_id_nitku": "1234567890123456789012",
                "street": "Jl. Sudirman No. 1",
                "city": "Jakarta",
                "country_id": cls.env.ref("base.id").id,
            }
        )

        # --- Basic posted invoice ---
        cls.invoice = cls._create_posted_invoice()

    @classmethod
    def _create_posted_invoice(cls, name=None):
        """Create and post a standard out_invoice."""
        invoice = cls.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": cls.customer.id,
                "invoice_date": "2025-01-15",
                "l10n_id_kode_transaksi": "01",
                "l10n_id_termin_pembayaran": "NORMAL",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Jasa Konsultasi",
                            "quantity": 1.0,
                            "price_unit": 10_000_000.0,
                        },
                    )
                ],
            }
        )
        invoice.action_post()
        return invoice

    # ── Pre-built mock response helpers ────────────────────────────────

    @staticmethod
    def _resp_create_success(
        transaction_id="TXN-2025-001",
        no_faktur="010.001-25.00000001",
        status_transaksi="APPROVAL_SUKSES",
        status_faktur="NORMAL",
    ):
        return {
            "transactionId": transaction_id,
            "noInvoice": "INV/2025/00001",
            "statusTransaksi": status_transaksi,
            "statusFaktur": status_faktur,
            "nomorFaktur": no_faktur,
            "pdfUrl": f"https://sandbox.pajak.io/pdf/{transaction_id}.pdf",
        }

    @staticmethod
    def _resp_cancel_success(
        status_faktur="BATAL",
        pdf_url="https://sandbox.pajak.io/pdf/cancelled.pdf",
    ):
        return {
            "statusTransaksi": "APPROVAL_SUKSES",
            "statusFaktur": status_faktur,
            "pdfUrl": pdf_url,
        }

    @staticmethod
    def _resp_waiting_cancellation():
        return {
            "statusTransaksi": "APPROVAL_SUKSES",
            "statusFaktur": "MENUNGGU_PEMBATALAN",
            "pdfUrl": "",
        }

    @staticmethod
    def _resp_waiting_replacement():
        return {
            "statusTransaksi": "APPROVAL_SUKSES",
            "statusFaktur": "MENUNGGU_PENGGANTI",
            "nomorFaktur": "010.001-25.00000002",
            "pdfUrl": "",
        }

    @staticmethod
    def _mock_http_response(status_code=200, json_body=None, text=""):
        """Build a mock requests.Response object."""
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.ok = status_code < 400
        mock_resp.text = text
        if json_body is not None:
            mock_resp.json.return_value = json_body
        else:
            mock_resp.json.side_effect = ValueError("No JSON")
        return mock_resp

    @staticmethod
    def _mock_503():
        return TestPajakIoCommon._mock_http_response(
            status_code=503,
            text="pajak.io is currently under maintenance. Please try again later.",
        )

    @staticmethod
    def _mock_400_duplicate():
        return TestPajakIoCommon._mock_http_response(
            status_code=400,
            json_body={
                "code": 400,
                "status": "BAD_REQUEST",
                "message": "Duplicate noInvoice: invoice number already exists",
            },
        )

    # ── Patch context managers ──────────────────────────────────────────

    @contextmanager
    def _patch_service(self, method_name, return_value):
        """Patch PajakeIOService.<method_name> to return return_value directly."""
        with patch(
            f"{_SERVICE_PATH}.{method_name}", return_value=return_value
        ) as mock_method:
            yield mock_method

    @contextmanager
    def _patch_http(self, mock_response):
        """Patch the underlying requests.request call."""
        with patch(_REQUESTS_PATH, return_value=mock_response) as mock_req:
            yield mock_req

    # ── Fixture helpers ─────────────────────────────────────────────────

    def _create_approved_transaction(self, move, transaction_id="TXN-APPROVED-001", no_faktur="010.001-25.00000001"):
        """Create a pre-existing APPROVAL_SUKSES transaction on an invoice."""
        return self.env["l10n.id.pajak.io.transaction"].create(
            {
                "move_id": move.id,
                "transaction_id": transaction_id,
                "no_faktur": no_faktur,
                "no_invoice": move.name,
                "transaction_status": "APPROVAL_SUKSES",
                "invoice_status": "NORMAL",
                "is_replacement": False,
            }
        )

    def _run_submit_wizard(self, move, is_replacement=False, replaced_tx=None):
        """Create and run the submit wizard on the given invoice."""
        vals = {"move_id": move.id, "is_replacement": is_replacement}
        if replaced_tx:
            vals["replaced_transaction_id"] = replaced_tx.id
        wizard = self.env["l10n.id.pajak.io.submit.wizard"].create(vals)
        return wizard.action_submit()

    def _run_cancel_wizard(self, move):
        """Create and run the cancel wizard on the given invoice."""
        wizard = self.env["l10n.id.pajak.io.cancel.wizard"].create(
            {"move_id": move.id}
        )
        return wizard.action_cancel()
