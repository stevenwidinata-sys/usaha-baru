"""Aplikasi pencatatan usaha: pembelian, stok, penjualan, dan laporan keuangan."""
import os

from flask import Flask

from . import auth, db, util

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=None,  # diambil dari database (dibuat sekali) supaya sesi login tetap berlaku
        DATABASE=os.environ.get("USAHA_DATABASE") or os.path.join(ROOT, "data", "usaha.db"),
        SESSION_COOKIE_SECURE=os.environ.get("USAHA_HTTPS") == "1",
    )
    if test_config:
        app.config.update(test_config)
    os.makedirs(os.path.dirname(app.config["DATABASE"]), exist_ok=True)

    db.init_app(app)
    auth.init_app(app)
    app.register_blueprint(auth.bp)

    app.jinja_env.filters.update(
        rp=util.rupiah,
        rpk=util.rupiah_kurung,
        angka=util.angka,
        tgl=util.tanggal,
        tgl_panjang=util.tanggal_panjang,
        bulan_label=util.label_bulan,
        metode=lambda m: util.METODE_BAYAR.get(m, m),
    )

    from .routes import BLUEPRINTS
    from .routes.hutang import jumlah_hutang_telat

    @app.context_processor
    def konteks_umum():
        conn = db.get_db()
        return {
            "nama_usaha": db.ambil_pengaturan(conn, "nama_usaha", "Usaha Baru"),
            "hutang_telat": jumlah_hutang_telat(conn),
        }

    for bp in BLUEPRINTS:
        app.register_blueprint(bp)

    return app
