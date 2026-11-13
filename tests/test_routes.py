"""Uji alur lewat halaman web: semua halaman terbuka, transaksi tersimpan, laporan & CSV benar."""
import pytest


def isi_data(client):
    client.post("/modal", data={"jenis": "setoran", "tanggal": "2026-10-01", "jumlah": "5.000.000", "akun_id": "1"})
    client.post("/barang/baru", data={"kode": "BRG-001", "nama": "Beras 5 kg", "satuan": "karung",
                                      "harga_jual": "76000", "stok_minimum": "10"})
    client.post("/barang/baru", data={"kode": "BRG-002", "nama": "Minyak 2 L", "satuan": "pouch",
                                      "harga_jual": "37500", "stok_minimum": "12", "stok_awal": "4",
                                      "modal_awal": "33000", "tanggal_awal": "2026-10-01"})
    client.post("/pembelian/baru", data={"tanggal": "2026-10-02", "akun_id": "1", "pemasok": "CV A",
                                         "barang_id": ["1", "1"], "qty": ["10", "10"], "harga": ["10000", "12000"]})
    client.post("/penjualan/baru", data={"tanggal": "2026-10-05", "metode_bayar": "tunai", "akun_tunai": "1",
                                         "barang_id": ["1"], "qty": ["5"], "harga": ["15000"]})
    client.post("/penjualan/baru", data={"tanggal": "2026-10-06", "metode_bayar": "qris", "akun_nontunai": "3",
                                         "biaya_admin": "100", "barang_id": ["1", "2"], "qty": ["2", "1"],
                                         "harga": ["15000", "37500"]})
    client.post("/biaya", data={"tanggal": "2026-10-10", "kategori": "Sewa tempat", "jumlah": "50000",
                                "akun_id": "1"})


HALAMAN = [
    "/", "/?bulan=2026-10", "/barang", "/barang?f=isi", "/barang?nonaktif=1", "/barang/baru", "/barang/1",
    "/barang/1/edit", "/stok", "/stok?jenis=stok_awal", "/pembelian?bulan=2026-10", "/pembelian/baru",
    "/pembelian/1", "/pembelian/1/edit", "/penjualan?bulan=2026-10", "/penjualan/baru", "/penjualan/1",
    "/penjualan/2/edit", "/biaya?bulan=2026-10", "/biaya/1/edit", "/modal", "/pindah-dana",
    "/laporan/laba-rugi?bulan=2026-10", "/laporan/laba-rugi?mode=tahunan&tahun=2026",
    "/laporan/arus-kas?bulan=2026-10", "/laporan/arus-kas?mode=tahunan&tahun=2026",
    "/laporan/neraca?tanggal=2026-10-31", "/pengaturan",
]


def test_dashboard_kosong_menampilkan_panduan(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Mulai pakai" in r.get_data(as_text=True)


@pytest.mark.parametrize("url", HALAMAN)
def test_semua_halaman_terbuka(client, url):
    isi_data(client)
    r = client.get(url)
    assert r.status_code == 200, url


def test_laporan_laba_rugi_berisi_angka_benar(client):
    isi_data(client)
    teks = client.get("/laporan/laba-rugi?bulan=2026-10").get_data(as_text=True)
    # penjualan 75.000 + 30.000 + 37.500; HPP 7 x 11.000 + 33.000
    assert "Rp 142.500" in teks
    assert "Rp 110.000" in teks
    assert "Biaya admin pembayaran" in teks


def test_neraca_seimbang_lewat_halaman(client):
    isi_data(client)
    teks = client.get("/laporan/neraca?tanggal=2026-10-31").get_data(as_text=True)
    assert "Seimbang" in teks


def test_csv_laporan(client):
    isi_data(client)
    for url in ["/laporan/laba-rugi?bulan=2026-10&format=csv", "/laporan/laba-rugi?mode=tahunan&tahun=2026&format=csv",
                "/laporan/arus-kas?bulan=2026-10&format=csv", "/laporan/neraca?tanggal=2026-10-31&format=csv"]:
        r = client.get(url)
        assert r.status_code == 200
        assert r.mimetype == "text/csv"
        assert ";" in r.get_data(as_text=True)


def test_penjualan_melebihi_stok_ditolak(client):
    isi_data(client)
    r = client.post("/penjualan/baru", data={"tanggal": "2026-10-07", "metode_bayar": "tunai", "akun_tunai": "1",
                                             "barang_id": ["2"], "qty": ["99"], "harga": ["37500"]})
    assert "tidak cukup" in r.get_data(as_text=True)
    assert "PJ-0003" not in client.get("/penjualan?bulan=2026-10").get_data(as_text=True)


def test_hapus_pembelian_yang_terjual_ditolak(client):
    isi_data(client)
    r = client.post("/pembelian/1/hapus", follow_redirects=True)
    assert "tidak bisa dihapus" in r.get_data(as_text=True)


def test_pindah_dana_dan_backup(client):
    isi_data(client)
    r = client.post("/pindah-dana", data={"tanggal": "2026-10-20", "dari_akun_id": "1", "ke_akun_id": "2",
                                          "jumlah": "100000"}, follow_redirects=True)
    assert "Pindah dana Rp 100.000 dicatat" in r.get_data(as_text=True)
    r = client.get("/pengaturan/backup")
    assert r.status_code == 200
    assert r.data[:15] == b"SQLite format 3"
    r.close()
