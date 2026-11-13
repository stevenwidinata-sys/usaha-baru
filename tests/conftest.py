import pytest

from app import create_app
from app.db import connect, init_db


@pytest.fixture
def conn(tmp_path):
    c = connect(str(tmp_path / "tes.db"))
    init_db(c)
    yield c
    c.close()


@pytest.fixture
def app(tmp_path):
    return create_app({"DATABASE": str(tmp_path / "app.db"), "TESTING": True})


@pytest.fixture
def client(app):
    return app.test_client()


def buat_barang(conn, kode="B1", nama="Barang Satu", harga_jual=15000, minimum=0):
    return conn.execute(
        "INSERT INTO barang (kode, nama, satuan, harga_jual, stok_minimum) VALUES (?, ?, 'pcs', ?, ?)",
        (kode, nama, harga_jual, minimum),
    ).lastrowid


def akun_id(conn, jenis="tunai"):
    return conn.execute("SELECT id FROM akun WHERE jenis = ? ORDER BY id LIMIT 1", (jenis,)).fetchone()[0]
