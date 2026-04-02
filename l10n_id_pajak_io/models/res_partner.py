# Copyright 2025 Odoo Community Association (OCA)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    # Full 22-digit NITKU (Nomor Identitas Tempat Kegiatan Usaha).
    # Different from l10n_id_tku (6-digit branch code from l10n_id_efaktur_coretax).
    # Required by Pajak.io API as lawanTransaksi.nitku.
    # Use "0000000000000000000000" when identity type is NIK/PASPOR/LAINNYA.
    l10n_id_nitku = fields.Char(
        string="NITKU (22 digit)",
        size=22,
        help=(
            "Nomor Identitas Tempat Kegiatan Usaha — 22-digit business location "
            "code required by Pajak.io. Use all-zeros for non-NPWP identities."
        ),
    )
