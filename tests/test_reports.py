import pytest

from app import reports, services
from tests.conftest import akun_id, buat_barang


def setor(conn, tanggal, jumlah, jenis="tunai", tipe="setoran"):
    conn.execute(
        "INSERT INTO transaksi_modal (tanggal, jenis, jumlah, akun_id) VALUES (?, ?, ?, ?)",
        (tanggal, tipe, jumlah, akun_id(conn, jenis)),
    )


def biaya(conn, tanggal, kategori, jumlah):
    conn.execute(
        "INSERT INTO biaya (tanggal, kategori, jumlah, akun_id) VALUES (?, ?, ?, ?)",
        (tanggal, kategori, jumlah, akun_id(conn)),
    )


@pytest.fixture
def skenario(conn):
    """Setor 5 jt, beli 10@10.000 + 10@12.000, jual 5 tunai @15.000, jual 2 QRIS @15.000 (admin 100), sewa 50.000."""
    b = buat_barang(conn)
    setor(conn, "2026-10-01", 5_000_000)
    services.simpan_pembelian(conn, {"tanggal": "2026-10-02", "akun_id": akun_id(conn)},
                              [{"barang_id": b, "qty": 10, "harga": 10000}])
    services.simpan_pembelian(conn, {"tanggal": "2026-10-03", "akun_id": akun_id(conn)},
                              [{"barang_id": b, "qty": 10, "harga": 12000}])
    services.simpan_penjualan(conn, {"tanggal": "2026-10-05", "metode_bayar": "tunai", "akun_id": akun_id(conn)},
                              [{"barang_id": b, "qty": 5, "harga": 15000}])
    services.simpan_penjualan(
        conn,
        {"tanggal": "2026-10-06", "metode_bayar": "qris", "akun_id": akun_id(conn, "ewallet"), "biaya_admin": 100},
        [{"barang_id": b, "qty": 2, "harga": 15000}],
    )
    biaya(conn, "2026-10-10", "Sewa tempat", 50000)
    return b


def test_laba_rugi_bulanan(conn, skenario):
    lr = reports.laba_rugi_bulan(conn, "2026-10")
    assert lr["penjualan_bersih"] == 105000
    assert lr["hpp"] == 77000            # 7 x 11.000
    assert lr["laba_kotor"] == 28000
    assert dict(lr["biaya"]) == {"Sewa tempat": 50000, "Biaya admin pembayaran": 100}
    assert lr["laba_bersih"] == 28000 - 50100


def test_laba_rugi_tahunan(conn, skenario):
    th = reports.laba_rugi_tahunan(conn, 2026)
    assert len(th["bulan"]) == 12
    assert th["bulan"][9]["penjualan_bersih"] == 105000
    assert th["bulan"][0]["penjualan_bersih"] == 0
    assert th["total"]["laba_bersih"] == th["bulan"][9]["laba_bersih"]


def test_arus_kas_dan_saldo_akun(conn, skenario):
    ak = reports.arus_kas(conn, "2026-10-01", "2026-10-31")
    assert ak["saldo_awal"] == 0
    assert dict(ak["masuk"])["Setoran modal"] == 5_000_000
    assert ak["total_keluar"] == 220000 + 50100
    assert ak["saldo_akhir"] == 5_000_000 + 105000 - 220000 - 50100
    saldo = {a["jenis"]: a["saldo"] for a in ak["per_akun"]}
    assert saldo["ewallet"] == 30000 - 100


def test_pindah_dana_tidak_mengubah_total(conn, skenario):
    sebelum = reports.arus_kas(conn, "2026-10-01", "2026-10-31")["saldo_akhir"]
    conn.execute("INSERT INTO pindah_dana (tanggal, dari_akun_id, ke_akun_id, jumlah) VALUES (?, ?, ?, ?)",
                 ("2026-10-20", akun_id(conn), akun_id(conn, "bank"), 1_000_000))
    sesudah = reports.arus_kas(conn, "2026-10-01", "2026-10-31")
    assert sesudah["saldo_akhir"] == sebelum
    assert {a["jenis"]: a["saldo"] for a in sesudah["per_akun"]}["bank"] == 1_000_000


def test_neraca_seimbang(conn, skenario):
    b = skenario
    services.simpan_stok_awal(conn, "2026-10-01", buat_barang(conn, "B2", "Barang Dua"), 3, 7000)
    services.simpan_opname(conn, "2026-10-31", b, 12, "rusak")
    setor(conn, "2026-10-15", 200000, tipe="prive")
    n = reports.neraca(conn, "2026-10-31")
    assert n["persediaan"] == 12 * 11000 + 21000
    assert n["seimbang"], n
    assert n["stok_awal"] == 21000


def test_neraca_seimbang_dengan_hpp_pecahan(conn):
    b = buat_barang(conn)
    setor(conn, "2026-01-01", 1_000_000)
    services.simpan_pembelian(conn, {"tanggal": "2026-01-02", "akun_id": akun_id(conn)},
                              [{"barang_id": b, "qty": 3, "harga": 10000}])
    services.simpan_pembelian(conn, {"tanggal": "2026-01-03", "akun_id": akun_id(conn)},
                              [{"barang_id": b, "qty": 7, "harga": 10001}])
    for hari in range(4, 11):
        services.simpan_penjualan(conn, {"tanggal": f"2026-01-{hari:02d}", "metode_bayar": "tunai",
                                         "akun_id": akun_id(conn)}, [{"barang_id": b, "qty": 1, "harga": 13000}])
    assert reports.neraca(conn, "2026-01-31")["seimbang"]
    assert reports.neraca(conn, "2027-03-31")["seimbang"]
