"""Supaya aplikasi bisa dipasang di layar utama HP (Progressive Web App)."""
from flask import Blueprint, current_app, jsonify, send_from_directory, url_for

from ..db import ambil_pengaturan, get_db

bp = Blueprint("pwa", __name__)


@bp.get("/manifest.webmanifest")
def manifest():
    nama = ambil_pengaturan(get_db(), "nama_usaha", "Usaha Baru")
    ikon = lambda f: url_for("static", filename=f"ikon/{f}")  # noqa: E731
    resp = jsonify({
        "name": nama,
        "short_name": nama[:12],
        "description": "Pencatatan pembelian, stok, penjualan, dan laporan keuangan",
        "lang": "id",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#F4F5F2",
        "theme_color": "#10231C",
        "icons": [
            {"src": ikon("ikon-192.png"), "sizes": "192x192", "type": "image/png"},
            {"src": ikon("ikon-512.png"), "sizes": "512x512", "type": "image/png"},
            {"src": ikon("ikon-maskable-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
        "shortcuts": [
            {"name": "Penjualan baru", "url": "/penjualan/baru"},
            {"name": "Pembelian baru", "url": "/pembelian/baru"},
        ],
    })
    resp.mimetype = "application/manifest+json"
    return resp


@bp.get("/sw.js")
def service_worker():
    resp = send_from_directory(current_app.static_folder, "sw.js", mimetype="text/javascript", max_age=0)
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-cache"
    return resp
