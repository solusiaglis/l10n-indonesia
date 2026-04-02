# Copyright 2025 Odoo Community Association (OCA)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
import base64
import logging

import requests

from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_BASE_URLS = {
    "sandbox": "https://sandbox-openapi.pajak.io",
    "production": "https://openapi.pajak.io",
}

# Map Odoo l10n_id_kode_transaksi ('01'..'09') → Pajak.io kdJenisTransaksi
KODE_TRANSAKSI_MAP = {
    "01": "TD.00301",
    "02": "TD.00302",
    "03": "TD.00303",
    "04": "TD.00304",
    "05": "TD.00305",
    "06": "TD.00306",
    "07": "TD.00307",
    "08": "TD.00308",
    "09": "TD.00309",
    "10": "TD.00310",
}

# Map Odoo buyer document type → Pajak.io identityType
IDENTITY_TYPE_MAP = {
    "TIN": "NPWP",
    "NIK": "NIK",
    "Passport": "PASPOR",
    "Others": "LAINNYA",
}


class PajakeIOService:
    """Plain Python HTTP client for the Pajak.io OpenAPI.

    Instantiate via ``config.get_service()`` where config is an
    ``l10n.id.pajak.io.config`` record.
    """

    def __init__(self, config):
        self.config = config
        self.base_url = _BASE_URLS[config.environment]
        self.timeout = config.request_timeout
        self.logging_enabled = config.logging_enabled
        self._headers = self._build_headers(config.api_key)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_headers(api_key):
        encoded = base64.b64encode(api_key.encode()).decode()
        return {
            "Authorization": f"API Key {encoded}",
            "Content-Type": "application/json",
        }

    def _call(self, method, path, payload=None):
        url = f"{self.base_url}{path}"
        if self.logging_enabled:
            _logger.info("Pajak.io → %s %s | payload: %s", method, url, payload)
        try:
            resp = requests.request(
                method,
                url,
                json=payload,
                headers=self._headers,
                timeout=self.timeout,
            )
        except requests.exceptions.Timeout as exc:
            raise UserError(
                "Pajak.io request timed out. Please try again."
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise UserError(
                f"Network error contacting Pajak.io: {exc}"
            ) from exc

        if self.logging_enabled:
            _logger.info("Pajak.io ← %s | body: %s", resp.status_code, resp.text)

        if resp.status_code == 503:
            raise UserError(
                "Pajak.io is currently under maintenance. Please try again later."
            )
        if not resp.ok:
            self._raise_api_error(resp)

        return resp.json()

    @staticmethod
    def _raise_api_error(resp):
        try:
            body = resp.json()
            msg = body.get("message") or str(body)
        except Exception:
            msg = resp.text or f"HTTP {resp.status_code}"
        raise UserError(f"Pajak.io API error ({resp.status_code}): {msg}")

    # ------------------------------------------------------------------
    # VAT Output (Faktur Keluaran) endpoints
    # ------------------------------------------------------------------

    def create_vat_output(self, payload):
        """POST /efaktur/v3/penjualan — Create a single VAT Output."""
        result = self._call("POST", "/efaktur/v3/penjualan", payload)
        return result.get("data", {})

    def update_vat_output(self, payload):
        """PUT /efaktur/v3/penjualan — Update a DRAFT VAT Output."""
        result = self._call("PUT", "/efaktur/v3/penjualan", payload)
        return result.get("data", {})

    def get_detail(self, transaction_id):
        """POST /efaktur/v3/penjualan/{transactionId} — Get invoice detail."""
        result = self._call("POST", f"/efaktur/v3/penjualan/{transaction_id}")
        return result.get("data", {})

    def get_pdf(self, transaction_id):
        """POST /efaktur/v3/penjualan/get-pdf — Get Base64-encoded PDF."""
        result = self._call(
            "POST",
            "/efaktur/v3/penjualan/get-pdf",
            {"transactionId": transaction_id},
        )
        return result.get("data", {}).get("filePdf", "")

    def cancel_vat_output(self, transaction_id):
        """POST /efaktur/v3/penjualan/batal — Cancel an APPROVAL_SUKSES invoice."""
        result = self._call(
            "POST",
            "/efaktur/v3/penjualan/batal",
            {"transactionId": transaction_id},
        )
        return result.get("data", {})

    def delete_vat_output(self, transaction_id):
        """POST /efaktur/v3/penjualan/hapus — Delete DRAFT or DITOLAK invoice."""
        result = self._call(
            "POST",
            "/efaktur/v3/penjualan/hapus",
            {"transactionId": transaction_id},
        )
        return result.get("data", {})

    def upload_to_djp(self, transaction_id):
        """POST /efaktur/v3/penjualan/upload — Upload DRAFT invoice to DGT."""
        result = self._call(
            "POST",
            "/efaktur/v3/penjualan/upload",
            {"transactionId": transaction_id},
        )
        return result.get("data", {})
