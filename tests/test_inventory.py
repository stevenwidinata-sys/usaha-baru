import pytest

from app import services
from app.inventory import StokTidakCukup, kartu_stok, nilai_persediaan, posisi_stok, stok_barang
from tests.conftest import akun_id, buat_barang


def beli(conn, tanggal, barang_id, qty, harga):
    return services.simpan_pembelian(
        conn, {"tanggal": tanggal, "akun_id": akun_id(conn)}, [{"barang_id": barang_id, "qty": qty, "harga": harga}]
    )


def jual(conn, tanggal, barang_id, qty, harga=15000, metode="tunai"):
    return services.simpan_penjualan(
        conn,
        {"tanggal": tanggal, "metode_bayar": metode, "akun_id": akun_id(conn)},
        [{"barang_id": barang_id, "qty": qty, "harga": harga}],
    )


def hpp_penjualan(conn, penjualan_id):
    return conn.execute("SELECT hpp_satuan FROM penjualan_item WHERE penjualan_id = ?", (penjualan_id,)).fetchone()[0]


def test_hpp_rata_rata_tertimbang(conn):
    b = buat_barang(conn)
    beli(conn, "2026-10-01", b, 10, 10000)
    beli(conn, "2026-10-02", b, 10, 12000)
    pj = jual(conn, "2026-10-03", b, 5)
    assert hpp_penjualan(conn, pj) == pytest.approx(11000)
    stok, hpp = stok_barang(conn, b)
    assert stok == 15
    assert hpp == pytest.approx(11000)
    assert nilai_persediaan(conn) == pytest.approx(165000)


def test_pembelian_bertanggal_mundur_mengubah_hpp_penjualan(conn):
    b = buat_barang(conn)
    beli(conn, "2026-10-01", b, 10, 10000)
    pj = jual(conn, "2026-10-05", b, 5)
    assert hpp_penjualan(conn, pj) == pytest.approx(10000)

    beli(conn, "2026-10-03", b, 10, 13000)
    assert hpp_penjualan(conn, pj) == pytest.approx(11500)


def test_edit_pembelian_menghitung_ulang(conn):
    b = buat_barang(conn)
    pb = beli(conn, "2026-10-01", b, 10, 10000)
    pj = jual(conn, "2026-10-02", b, 4)
    services.simpan_pembelian(
        conn, {"tanggal": "2026-10-01", "akun_id": akun_id(conn)}, [{"barang_id": b, "qty": 10, "harga": 9000}], pb
    )
    assert hpp_penjualan(conn, pj) == pytest.approx(9000)
    assert stok_barang(conn, b)[0] == 6


def test_penjualan_melebihi_stok_ditolak(conn):
    b = buat_barang(conn)
    beli(conn, "2026-10-01", b, 3, 10000)
    with pytest.raises(StokTidakCukup):
        jual(conn, "2026-10-02", b, 5)


def test_penjualan_sebelum_pembelian_ditolak(conn):
    b = buat_barang(conn)
    beli(conn, "2026-10-10", b, 10, 10000)
    with pytest.raises(StokTidakCukup):
        jual(conn, "2026-10-05", b, 1)


def test_hapus_pembelian_yang_sudah_terjual_ditolak(conn):
    b = buat_barang(conn)
    pb = beli(conn, "2026-10-01", b, 10, 10000)
    jual(conn, "2026-10-02", b, 8)
    with pytest.raises(StokTidakCukup):
        services.hapus_pembelian(conn, pb)


def test_pembelian_dan_penjualan_di_hari_yang_sama(conn):
    b = buat_barang(conn)
    beli(conn, "2026-10-01", b, 5, 10000)
    pj = jual(conn, "2026-10-01", b, 2)
    assert hpp_penjualan(conn, pj) == pytest.approx(10000)


def test_stok_awal_dan_opname(conn):
    b = buat_barang(conn)
    services.simpan_stok_awal(conn, "2026-10-01", b, 10, 10000)
    services.simpan_opname(conn, "2026-10-31", b, 8, "rusak")
    stok, hpp = stok_barang(conn, b)
    assert stok == 8
    assert hpp == pytest.approx(10000)
    row = conn.execute("SELECT keluar, nilai_mutasi FROM mutasi_stok WHERE sumber = 'opname'").fetchone()
    assert row["keluar"] == 2
    assert row["nilai_mutasi"] == pytest.approx(20000)


def test_opname_tanpa_selisih_ditolak(conn):
    b = buat_barang(conn)
    services.simpan_stok_awal(conn, "2026-10-01", b, 10, 10000)
    with pytest.raises(services.InputTidakValid):
        services.simpan_opname(conn, "2026-10-02", b, 10)


def test_status_stok(conn):
    b1 = buat_barang(conn, "A", "Aman", minimum=5)
    b2 = buat_barang(conn, "B", "Menipis", minimum=5)
    buat_barang(conn, "C", "Habis", minimum=5)
    beli(conn, "2026-10-01", b1, 10, 1000)
    beli(conn, "2026-10-01", b2, 3, 1000)
    status = {b["nama"]: b["status"] for b in posisi_stok(conn)}
    assert status == {"Aman": "aman", "Menipis": "menipis", "Habis": "habis"}


def test_kartu_stok_saldo_awal_periode(conn):
    b = buat_barang(conn)
    beli(conn, "2026-09-15", b, 10, 10000)
    jual(conn, "2026-10-02", b, 3)
    kartu = kartu_stok(conn, b, "2026-10-01", "2026-10-31")
    assert kartu["saldo_awal"] == 10
    assert len(kartu["mutasi"]) == 1
    assert kartu["mutasi"][0]["saldo_qty"] == 7


def test_nomor_nota_berurutan(conn):
    b = buat_barang(conn)
    beli(conn, "2026-10-01", b, 10, 10000)
    p1 = jual(conn, "2026-10-02", b, 1)
    p2 = jual(conn, "2026-10-02", b, 1)
    nota = [r[0] for r in conn.execute("SELECT no_nota FROM penjualan WHERE id IN (?, ?) ORDER BY id", (p1, p2))]
    assert nota == ["PJ-0001", "PJ-0002"]
