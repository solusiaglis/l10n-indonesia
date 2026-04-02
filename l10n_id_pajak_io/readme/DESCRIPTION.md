Modul ini mengintegrasikan Odoo dengan **Pajak.io OpenAPI** untuk mengirimkan dan mengelola
Faktur Pajak Keluaran (e-Faktur) secara langsung dari dalam Odoo.

Fitur utama:

- Submit Faktur Pajak Keluaran ke Pajak.io dari invoice Odoo
- Dukungan faktur pengganti (pengganti / replacement)
- Pembatalan faktur dengan deteksi status menunggu persetujuan pembeli
- Polling status asinkron (Refresh Status) untuk faktur yang menunggu konfirmasi DJP/pembeli
- Dukungan kode transaksi 07 dan 08 dengan keterangan tambahan
- Unduh PDF e-Faktur langsung dari Odoo
- Multi-company: setiap perusahaan dapat memiliki konfigurasi API Key sendiri
- Mode Sandbox dan Production
- Logging opsional untuk debugging request/response API
