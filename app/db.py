"""Koneksi SQLite dan inisialisasi skema."""
import os
import secrets
import sqlite3

from flask import current_app, g

SCHEMA = os.path.join(os.path.dirname(__file__), "schema.sql")

AKUN_DEFAULT = [
    ("Kas tunai", "tunai"),
    ("Rekening bank utama", "bank"),
    ("E-wallet usaha", "ewallet"),
]
KATEGORI_BIAYA_DEFAULT = [
    "Sewa tempat",
    "Listrik & air",
    "Gaji karyawan",
    "Transportasi",
    "Biaya admin pembayaran",
    "Lain-lain",
]
KATEGORI_ADMIN = "Biaya admin pembayaran"


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def _kolom(conn, tabel):
    return {r[1] for r in conn.execute(f"PRAGMA table_info({tabel})")}


def _migrasi(conn):
    """Tambahkan kolom baru ke database lama sebelum schema.sql (yang membuat ulang view) dijalankan."""
    kolom = _kolom(conn, "pembelian")
    if not kolom:
        return  # database baru, tabel dibuat lengkap oleh schema.sql
    tambahan = {
        "cara_bayar": "TEXT NOT NULL DEFAULT 'lunas' CHECK (cara_bayar IN ('lunas', 'tempo'))",
        "jatuh_tempo": "TEXT",
        "uang_muka": "INTEGER NOT NULL DEFAULT 0 CHECK (uang_muka >= 0)",
    }
    for nama, definisi in tambahan.items():
        if nama not in kolom:
            conn.execute(f"ALTER TABLE pembelian ADD COLUMN {nama} {definisi}")
    conn.commit()


def init_db(conn):
    _migrasi(conn)
    with open(SCHEMA, encoding="utf-8") as f:
        conn.executescript(f.read())
    if conn.execute("SELECT COUNT(*) FROM akun").fetchone()[0] == 0:
        conn.executemany("INSERT INTO akun (nama, jenis) VALUES (?, ?)", AKUN_DEFAULT)
    if conn.execute("SELECT COUNT(*) FROM kategori_biaya").fetchone()[0] == 0:
        conn.executemany("INSERT INTO kategori_biaya (nama) VALUES (?)", [(k,) for k in KATEGORI_BIAYA_DEFAULT])
    conn.execute("INSERT OR IGNORE INTO pengaturan (kunci, nilai) VALUES ('nama_usaha', 'Usaha Baru')")
    conn.commit()


def ambil_pengaturan(conn, kunci, default=""):
    row = conn.execute("SELECT nilai FROM pengaturan WHERE kunci = ?", (kunci,)).fetchone()
    return row["nilai"] if row else default


def simpan_pengaturan(conn, kunci, nilai):
    conn.execute(
        "INSERT INTO pengaturan (kunci, nilai) VALUES (?, ?) "
        "ON CONFLICT(kunci) DO UPDATE SET nilai = excluded.nilai",
        (kunci, nilai),
    )


def init_app(app):
    """Siapkan database, kunci sesi yang tetap (supaya login tidak hilang saat server restart),
    dan password awal dari variabel lingkungan USAHA_PASSWORD bila belum ada password."""
    from werkzeug.security import generate_password_hash

    app.teardown_appcontext(close_db)
    conn = connect(app.config["DATABASE"])
    try:
        init_db(conn)
        if not ambil_pengaturan(conn, "secret_key"):
            simpan_pengaturan(conn, "secret_key", secrets.token_hex(32))
        password_awal = os.environ.get("USAHA_PASSWORD")
        if password_awal and not ambil_pengaturan(conn, "password_hash"):
            simpan_pengaturan(conn, "password_hash", generate_password_hash(password_awal))
        conn.commit()
        if not app.config.get("SECRET_KEY"):
            app.config["SECRET_KEY"] = ambil_pengaturan(conn, "secret_key")
    finally:
        conn.close()
