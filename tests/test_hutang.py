import sqlite3

import pytest

from app import reports, services
from app.db import connect, init_db
from app.inventory import stok_barang
from tests.conftest import akun_id, buat_barang


def beli_tempo(conn, b, tanggal="2026-10-01", jatuh_tempo="2026-10-15", uang_muka=0, qty=10, harga=10000):
    return services.simpan_pembelian(
        conn,
        {"tanggal": tanggal, "akun_id": akun_id(conn), "cara_bayar": "tempo", "jatuh_tempo": jatuh_tempo,
         "uang_muka": uang_muka, "pemasok": "CV A"},
        [{"barang_id": b, "qty": qty, "harga": harga}],
    )


def saldo_total(conn, per="2026-12-31"):
    return sum(a["saldo"] for a in reports.saldo_akun(conn, per))


@pytest.fixture
def b(conn):
    conn.execute("INSERT INTO transaksi_modal (tanggal, jenis, jumlah, akun_id) VALUES ('2026-09-01', 'setoran', "
                 "1000000, ?)", (akun_id(conn),))
    return buat_barang(conn)


def test_pembelian_tempo_menambah_stok_tanpa_mengurangi_kas(conn, b):
    pb = beli_tempo(conn, b, uang_muka=30000)
    assert stok_barang(conn, b)[0] == 10
    assert saldo_total(conn) == 1_000_000 - 30000
    assert services.sisa_hutang(conn, pb) == 70000


def test_bayar_hutang_dicicil_sampai_lunas(conn, b):
    pb = beli_tempo(conn, b)
    services.bayar_hutang(conn, pb, "2026-10-05", 40000, akun_id(conn, "bank"))
    assert services.sisa_hutang(conn, pb) == 60000
    services.bayar_hutang(conn, pb, "2026-10-10", 60000, akun_id(conn))
    assert services.sisa_hutang(conn, pb) == 0
    with pytest.raises(services.InputTidakValid):
        services.bayar_hutang(conn, pb, "2026-10-11", 1, akun_id(conn))


def test_bayar_melebihi_sisa_atau_sebelum_tanggal_ditolak(conn, b):
    pb = beli_tempo(conn, b, tanggal="2026-10-05")
    with pytest.raises(services.InputTidakValid):
        services.bayar_hutang(conn, pb, "2026-10-06", 100001, akun_id(conn))
    with pytest.raises(services.InputTidakValid):
        services.bayar_hutang(conn, pb, "2026-10-04", 1000, akun_id(conn))


def test_validasi_form_tempo(conn, b):
    with pytest.raises(services.InputTidakValid):
        beli_tempo(conn, b, jatuh_tempo=None)
    with pytest.raises(services.InputTidakValid):
        beli_tempo(conn, b, tanggal="2026-10-10", jatuh_tempo="2026-10-01")
    with pytest.raises(services.InputTidakValid):
        beli_tempo(conn, b, uang_muka=100000)  # DP = total -> harusnya pilih lunas


def test_edit_pembelian_yang_sudah_dicicil(conn, b):
    pb = beli_tempo(conn, b)
    services.bayar_hutang(conn, pb, "2026-10-05", 80000, akun_id(conn))
    data = {"tanggal": "2026-10-01", "akun_id": akun_id(conn), "cara_bayar": "lunas"}
    with pytest.raises(services.InputTidakValid):
        services.simpan_pembelian(conn, data, [{"barang_id": b, "qty": 10, "harga": 10000}], pb)
    data.update(cara_bayar="tempo", jatuh_tempo="2026-10-15")
    with pytest.raises(services.InputTidakValid):  # total turun jadi 50.000 < 80.000 yang sudah dibayar
        services.simpan_pembelian(conn, data, [{"barang_id": b, "qty": 5, "harga": 10000}], pb)


def test_hapus_pembelian_ikut_menghapus_pembayaran(conn, b):
    pb = beli_tempo(conn, b)
    services.bayar_hutang(conn, pb, "2026-10-05", 10000, akun_id(conn))
    services.hapus_pembelian(conn, pb)
    assert conn.execute("SELECT COUNT(*) FROM pembayaran_hutang").fetchone()[0] == 0


def test_status_jatuh_tempo(conn, b):
    beli_tempo(conn, b, jatuh_tempo="2026-10-10")
    beli_tempo(conn, b, jatuh_tempo="2026-10-16")
    beli_tempo(conn, b, jatuh_tempo="2026-11-30")
    status = [(h["status"], h["keterangan"]) for h in reports.daftar_hutang(conn, acuan="2026-10-15")]
    assert status == [("telat", "Terlambat 5 hari"), ("dekat", "Besok"), ("aman", "46 hari lagi")]
    ring = reports.ringkasan_hutang(reports.daftar_hutang(conn, acuan="2026-10-15"))
    assert ring["total"] == 300000
    assert ring["telat"] == {"jumlah": 100000, "faktur": 1}


def test_neraca_seimbang_dengan_hutang(conn, b):
    pb = beli_tempo(conn, b, uang_muka=20000)
    services.simpan_penjualan(conn, {"tanggal": "2026-10-03", "metode_bayar": "tunai", "akun_id": akun_id(conn)},
                              [{"barang_id": b, "qty": 4, "harga": 15000}])
    services.bayar_hutang(conn, pb, "2026-10-20", 50000, akun_id(conn))
    sebelum = reports.neraca(conn, "2026-10-10")
    assert sebelum["hutang"] == 80000
    assert sebelum["seimbang"], sebelum
    sesudah = reports.neraca(conn, "2026-10-31")
    assert sesudah["hutang"] == 30000
    assert sesudah["seimbang"], sesudah


def test_arus_kas_mencatat_dp_dan_pembayaran_hutang(conn, b):
    pb = beli_tempo(conn, b, uang_muka=20000)
    services.bayar_hutang(conn, pb, "2026-10-20", 50000, akun_id(conn))
    keluar = dict(reports.arus_kas(conn, "2026-10-01", "2026-10-31")["keluar"])
    assert keluar["Pembelian barang (lunas & uang muka)"] == 20000
    assert keluar["Pembayaran hutang pemasok"] == 50000


def test_migrasi_database_lama(tmp_path):
    path = str(tmp_path / "lama.db")
    lama = sqlite3.connect(path)
    lama.executescript(
        "CREATE TABLE akun (id INTEGER PRIMARY KEY, nama TEXT NOT NULL UNIQUE, jenis TEXT NOT NULL, aktif INTEGER "
        "NOT NULL DEFAULT 1);"
        "INSERT INTO akun (nama, jenis) VALUES ('Kas tunai', 'tunai');"
        "CREATE TABLE pembelian (id INTEGER PRIMARY KEY, tanggal TEXT NOT NULL, no_faktur TEXT, pemasok TEXT, "
        "akun_id INTEGER NOT NULL REFERENCES akun(id), catatan TEXT);"
        "INSERT INTO pembelian (tanggal, akun_id) VALUES ('2026-10-01', 1);"
    )
    lama.commit()
    lama.close()
    conn = connect(path)
    init_db(conn)
    row = conn.execute("SELECT cara_bayar, jatuh_tempo, uang_muka FROM pembelian").fetchone()
    assert tuple(row) == ("lunas", None, 0)
    conn.close()
