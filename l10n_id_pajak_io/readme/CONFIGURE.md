1. Pastikan modul `l10n_id_efaktur_coretax` sudah terinstal.
2. Dapatkan API Key dari tim support Pajak.io (satu token per NPWP perusahaan).
3. Buka **Accounting → Konfigurasi → Pajak.io** dan buat konfigurasi baru:
   - Pilih environment **Sandbox** untuk pengujian atau **Production** untuk live.
   - Masukkan API Key (token mentah, bukan yang sudah di-encode).
   - Atur **Auto Upload to DJP** sesuai kebutuhan.
4. Hubungkan konfigurasi ke perusahaan melalui **Accounting → Konfigurasi → Perusahaan**.
5. Pada setiap partner, lengkapi field **NITKU (22 digit)** untuk identitas tempat usaha.
6. Gunakan tombol **Test Koneksi** pada form konfigurasi untuk memverifikasi koneksi.
