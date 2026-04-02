# Copyright 2025 Odoo Community Association (OCA)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import TestPajakIoCommon


@tagged("post_install", "-at_install", "pajak_io")
class TestPajakIoScenarios(TestPajakIoCommon):
    """9 Pajak.io integration scenarios.

    All API calls are mocked — no real network access required.
    """

    # =========================================================================
    # Scenario 1: Create a normal tax invoice
    # Expected: transaction record created with transactionId, NORMAL status,
    #           nomorFaktur, and pdfUrl populated.
    # =========================================================================
    def test_01_create_normal_invoice(self):
        resp = self._resp_create_success(
            transaction_id="TXN-S01",
            no_faktur="010.001-25.10000001",
            status_transaksi="APPROVAL_SUKSES",
            status_faktur="NORMAL",
        )
        with self._patch_service("create_vat_output", resp):
            self._run_submit_wizard(self.invoice)

        tx = self.invoice.pajak_io_transaction_ids[:1]
        self.assertTrue(tx, "Harus ada transaction record setelah submit")
        self.assertEqual(tx.transaction_id, "TXN-S01")
        self.assertEqual(tx.invoice_status, "NORMAL")
        self.assertEqual(tx.no_faktur, "010.001-25.10000001")
        self.assertTrue(tx.pdf_url)
        self.assertEqual(self.invoice.pajak_io_status, "approved")

    # =========================================================================
    # Scenario 2: Cancel a normal tax invoice
    # Expected: invoice_status = BATAL, pdf_url updated.
    # =========================================================================
    def test_02_cancel_normal_invoice(self):
        invoice2 = self._create_posted_invoice()
        self._create_approved_transaction(
            invoice2,
            transaction_id="TXN-S02",
            no_faktur="010.001-25.10000002",
        )

        resp = self._resp_cancel_success(
            status_faktur="BATAL",
            pdf_url="https://sandbox.pajak.io/pdf/s02-cancelled.pdf",
        )
        with self._patch_service("cancel_vat_output", resp):
            self._run_cancel_wizard(invoice2)

        tx = invoice2.pajak_io_transaction_ids[:1]
        self.assertEqual(tx.invoice_status, "BATAL")
        self.assertTrue(tx.pdf_url)
        self.assertEqual(invoice2.pajak_io_status, "cancelled")

    # =========================================================================
    # Scenario 3: Create with a duplicate invoice number
    # Expected: UserError raised mentioning duplicate / already exists.
    # =========================================================================
    def test_03_duplicate_invoice_number_raises_error(self):
        with self._patch_http(self._mock_400_duplicate()):
            with self.assertRaises(UserError) as cm:
                self._run_submit_wizard(self.invoice)
        self.assertIn("400", str(cm.exception))

    # =========================================================================
    # Scenario 4: Create a replacement tax invoice
    # Expected: is_replacement=True on tx, new nomorFaktur, status MENUNGGU_PENGGANTI.
    # =========================================================================
    def test_04_create_replacement_invoice(self):
        invoice4 = self._create_posted_invoice()
        original_tx = self._create_approved_transaction(
            invoice4,
            transaction_id="TXN-S04-ORIG",
            no_faktur="010.001-25.10000004",
        )

        replacement_invoice = self._create_posted_invoice()
        resp = self._resp_create_success(
            transaction_id="TXN-S04-REPL",
            no_faktur="010.001-25.10000004R",
            status_transaksi="APPROVAL_SUKSES",
            status_faktur="NORMAL_PENGGANTI",
        )
        with self._patch_service("create_vat_output", resp):
            self._run_submit_wizard(
                replacement_invoice,
                is_replacement=True,
                replaced_tx=original_tx,
            )

        tx = replacement_invoice.pajak_io_transaction_ids[:1]
        self.assertTrue(tx.is_replacement)
        self.assertEqual(tx.replaced_no_faktur, "010.001-25.10000004")
        self.assertEqual(tx.invoice_status, "NORMAL_PENGGANTI")
        self.assertEqual(tx.no_faktur, "010.001-25.10000004R")

    # =========================================================================
    # Scenario 5: Cancel a replacement tax invoice
    # Expected: Same as Scenario 2 but on a replacement transaction.
    # =========================================================================
    def test_05_cancel_replacement_invoice(self):
        invoice5 = self._create_posted_invoice()
        tx5 = self.env["l10n.id.pajak.io.transaction"].create(
            {
                "move_id": invoice5.id,
                "transaction_id": "TXN-S05-REPL",
                "no_faktur": "010.001-25.10000005R",
                "no_invoice": invoice5.name,
                "transaction_status": "APPROVAL_SUKSES",
                "invoice_status": "NORMAL_PENGGANTI",
                "is_replacement": True,
                "replaced_no_faktur": "010.001-25.10000005",
            }
        )

        resp = self._resp_cancel_success(
            status_faktur="BATAL",
            pdf_url="https://sandbox.pajak.io/pdf/s05-repl-cancelled.pdf",
        )
        with self._patch_service("cancel_vat_output", resp):
            self._run_cancel_wizard(invoice5)

        tx5.invalidate_recordset()
        self.assertEqual(tx5.invoice_status, "BATAL")
        self.assertTrue(tx5.pdf_url)
        self.assertEqual(invoice5.pajak_io_status, "cancelled")

    # =========================================================================
    # Scenario 6: Cancel an invoice that has been credited by the buyer
    # Expected: status becomes MENUNGGU_PEMBATALAN immediately after cancel call.
    #           After buyer approves (simulated by refresh), status → BATAL.
    # =========================================================================
    def test_06_cancel_invoice_credited_by_buyer(self):
        invoice6 = self._create_posted_invoice()
        self._create_approved_transaction(
            invoice6,
            transaction_id="TXN-S06",
            no_faktur="010.001-25.10000006",
        )

        # Step 1: Cancel returns "waiting for cancellation"
        with self._patch_service("cancel_vat_output", self._resp_waiting_cancellation()):
            self._run_cancel_wizard(invoice6)

        tx6 = invoice6.pajak_io_transaction_ids[:1]
        self.assertEqual(tx6.invoice_status, "MENUNGGU_PEMBATALAN")
        self.assertEqual(invoice6.pajak_io_status, "waiting_cancellation")

        # Step 2: Buyer approves → Refresh Status returns BATAL
        detail_after_approval = {
            "statusTransaksi": "APPROVAL_SUKSES",
            "statusFaktur": "BATAL",
            "urlPdf": "https://sandbox.pajak.io/pdf/s06-cancelled.pdf",
        }
        with self._patch_service("get_detail", detail_after_approval):
            invoice6.action_pajak_io_refresh_status()

        tx6.invalidate_recordset()
        self.assertEqual(tx6.invoice_status, "BATAL")
        self.assertEqual(invoice6.pajak_io_status, "cancelled")

    # =========================================================================
    # Scenario 7: Create a replacement invoice for one already credited by buyer
    # Expected: status MENUNGGU_PENGGANTI; after poll → DIGANTI.
    # =========================================================================
    def test_07_replace_invoice_credited_by_buyer(self):
        invoice7_orig = self._create_posted_invoice()
        original_tx = self._create_approved_transaction(
            invoice7_orig,
            transaction_id="TXN-S07-ORIG",
            no_faktur="010.001-25.10000007",
        )

        invoice7_repl = self._create_posted_invoice()

        # Submit replacement → API returns MENUNGGU_PENGGANTI (buyer has credited)
        resp = self._resp_create_success(
            transaction_id="TXN-S07-REPL",
            no_faktur="010.001-25.10000007R",
            status_transaksi="APPROVAL_SUKSES",
            status_faktur="MENUNGGU_PENGGANTI",
        )
        with self._patch_service("create_vat_output", resp):
            self._run_submit_wizard(
                invoice7_repl,
                is_replacement=True,
                replaced_tx=original_tx,
            )

        tx7 = invoice7_repl.pajak_io_transaction_ids[:1]
        self.assertEqual(tx7.invoice_status, "MENUNGGU_PENGGANTI")
        self.assertEqual(invoice7_repl.pajak_io_status, "waiting_replacement")

        # Buyer approves → refresh shows DIGANTI
        detail_after_approval = {
            "statusTransaksi": "APPROVAL_SUKSES",
            "statusFaktur": "DIGANTI",
            "pdfUrl": "https://sandbox.pajak.io/pdf/s07-replaced.pdf",
        }
        with self._patch_service("get_detail", detail_after_approval):
            invoice7_repl.action_pajak_io_refresh_status()

        tx7.invalidate_recordset()
        self.assertEqual(tx7.invoice_status, "DIGANTI")

    # =========================================================================
    # Scenario 8: Create a normal invoice type 07/08 with additional info
    # Expected: payload sent to API includes keteranganTambahan with kode and
    #           nomorDokumenPendukung.
    # =========================================================================
    def test_08_create_invoice_type_07_with_keterangan_tambahan(self):
        invoice8 = self._create_posted_invoice()
        invoice8.write(
            {
                "l10n_id_kode_transaksi": "07",
                "l10n_id_coretax_add_info_07": "TD.00501",
                "l10n_id_coretax_custom_doc": "BKP-EXPORT-2025-001",
            }
        )

        captured_payload = {}

        def fake_create(payload):
            captured_payload.update(payload)
            return self._resp_create_success(
                transaction_id="TXN-S08",
                no_faktur="010.007-25.10000008",
                status_faktur="NORMAL",
            )

        from unittest.mock import patch

        svc_path = (
            "odoo.addons.l10n_id_pajak_io.models.pajak_io_service"
            ".PajakeIOService.create_vat_output"
        )
        with patch(svc_path, side_effect=fake_create):
            self._run_submit_wizard(invoice8)

        self.assertEqual(captured_payload.get("kdJenisTransaksi"), "TD.00307")
        kt = captured_payload.get("keteranganTambahan")
        self.assertIsNotNone(kt, "keteranganTambahan harus ada untuk kode transaksi 07")
        self.assertEqual(kt.get("kode"), "TD.00501")
        self.assertEqual(kt.get("nomorDokumenPendukung"), "BKP-EXPORT-2025-001")

        tx8 = invoice8.pajak_io_transaction_ids[:1]
        self.assertTrue(tx8)
        self.assertEqual(tx8.no_faktur, "010.007-25.10000008")

    # =========================================================================
    # Scenario 9: Handle Pajak.io maintenance period (HTTP 503)
    # Expected: UserError raised with "maintenance" in message.
    # =========================================================================
    def test_09_maintenance_503_raises_user_error(self):
        with self._patch_http(self._mock_503()):
            with self.assertRaises(UserError) as cm:
                self._run_submit_wizard(self.invoice)

        self.assertIn(
            "maintenance",
            str(cm.exception).lower(),
            "UserError harus menyebut 'maintenance'",
        )
