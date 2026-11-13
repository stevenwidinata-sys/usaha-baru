# Usaha Baru

Aplikasi pencatatan usaha berbasis web yang berjalan di komputer sendiri. Bisa dibuka dari browser di laptop, atau dari HP yang terhubung ke WiFi yang sama.

## Fitur

- **Barang & stok**: daftar barang, stok terkini, peringatan stok menipis, kartu stok per barang, stok awal, dan stok opname.
- **Pembelian**: satu transaksi bisa berisi banyak barang. Stok dan harga modal langsung diperbarui.
- **Penjualan**: form kasir multi-barang dengan pilihan bayar **tunai, transfer bank, QRIS/e-wallet, atau kartu debit**. Untuk tunai ada hitung kembalian, untuk non-tunai bisa dicatat potongan biaya admin.
- **Harga modal (HPP) rata-rata tertimbang**, dihitung otomatis. Transaksi yang diedit atau bertanggal mundur tetap menghasilkan angka yang benar. Penjualan yang melebihi stok ditolak.
- **Biaya operasional** per kategori, **modal & prive**, dan **pindah dana** antar akun (kas tunai, bank, e-wallet).
- **Laporan**: laba rugi bulanan & tahunan, arus kas, dan neraca (dengan pengecekan seimbang). Semua laporan bisa dicetak atau disimpan sebagai PDF, dan diunduh sebagai CSV untuk Excel.
- **Dashboard** dan **backup** data dengan sekali klik.

## Menjalankan

Butuh Python 3.10 atau lebih baru.

**Cara paling mudah (Windows):** klik dua kali `jalankan.bat`. Saat pertama kali, file ini menyiapkan semua kebutuhan, lalu membuka browser ke `http://localhost:5000`.

**Cara manual:**

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt     # Windows
.venv\Scripts\python run.py
```

Saat berjalan, terminal menampilkan alamat untuk dibuka dari HP, misalnya `http://192.168.1.10:5000`. Kalau tidak bisa dibuka dari HP, izinkan Python di Windows Firewall untuk jaringan privat.

Data tersimpan di `data/usaha.db`. Unduh backup secara rutin dari menu **Pengaturan & backup**.

## Langkah awal

1. Buka **Pengaturan**: isi nama usaha, lalu cek daftar akun (kas tunai, rekening bank, e-wallet).
2. Buka **Modal & prive**: catat saldo awal tiap akun sebagai setoran modal.
3. Buka **Stok barang**, lalu **Barang baru**: tambah barang, sekalian isi stok awal kalau barangnya sudah ada.
4. Catat pembelian, penjualan, dan biaya sehari-hari. Semua laporan terisi otomatis.

## Pengembangan

```bash
.venv\Scripts\python -m pytest       # jalankan tes
.venv\Scripts\python run.py --debug  # mode pengembangan (auto-reload)
```

Struktur singkat:

| Lokasi | Isi |
|---|---|
| `app/schema.sql` | Skema database SQLite |
| `app/inventory.py` | Perhitungan kartu stok & HPP rata-rata |
| `app/services.py` | Simpan/hapus transaksi yang memengaruhi stok |
| `app/reports.py` | Laba rugi, arus kas, neraca |
| `app/routes/` | Halaman web (Flask blueprint) |
| `app/templates/`, `app/static/` | Tampilan |
| `tests/` | Tes otomatis (pytest) |

Batasan saat ini: semua transaksi dianggap lunas (belum ada hutang/piutang) dan belum ada PPN.
