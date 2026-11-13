"""Pengaturan: nama usaha, akun kas/bank/e-wallet, kategori biaya, dan backup database."""
import os
import socket
import sqlite3
import tempfile
from datetime import datetime

from flask import Blueprint, after_this_request, current_app, flash, redirect, render_template, request, send_file, url_for

from .. import util
from ..db import KATEGORI_ADMIN, ambil_pengaturan, get_db, simpan_pengaturan
from ..reports import saldo_akun

bp = Blueprint("pengaturan", __name__, url_prefix="/pengaturan")


def _ip_lokal():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return None


@bp.get("")
def index():
    conn = get_db()
    kategori = conn.execute(
        "SELECT k.*, (SELECT COUNT(*) FROM biaya b WHERE b.kategori = k.nama) AS dipakai FROM kategori_biaya k ORDER BY id"
    ).fetchall()
    return render_template(
        "pengaturan.html",
        nama=ambil_pengaturan(conn, "nama_usaha", "Usaha Baru"),
        akun=saldo_akun(conn),
        kategori=kategori,
        kategori_admin=KATEGORI_ADMIN,
        jenis_akun=util.JENIS_AKUN,
        ip=_ip_lokal(),
        port=request.host.split(":")[-1] if ":" in request.host else "5000",
        lokasi_db=current_app.config["DATABASE"],
    )


@bp.post("/nama")
def simpan_nama():
    conn = get_db()
    nama = request.form.get("nama", "").strip()
    if not nama:
        flash("Nama usaha tidak boleh kosong.", "galat")
    else:
        simpan_pengaturan(conn, "nama_usaha", nama)
        conn.commit()
        flash("Nama usaha disimpan.", "sukses")
    return redirect(url_for("pengaturan.index"))


@bp.post("/akun")
def tambah_akun():
    conn = get_db()
    nama = request.form.get("nama", "").strip()
    jenis = request.form.get("jenis")
    if not nama or jenis not in util.JENIS_AKUN:
        flash("Isi nama dan jenis akun.", "galat")
    else:
        try:
            conn.execute("INSERT INTO akun (nama, jenis) VALUES (?, ?)", (nama, jenis))
            conn.commit()
            flash(f"Akun {nama} ditambahkan.", "sukses")
        except sqlite3.IntegrityError:
            flash(f"Akun {nama} sudah ada.", "galat")
    return redirect(url_for("pengaturan.index") + "#akun")


@bp.post("/akun/<int:akun_id>")
def ubah_akun(akun_id):
    conn = get_db()
    if request.form.get("aksi") == "aktif":
        conn.execute("UPDATE akun SET aktif = 1 - aktif WHERE id = ?", (akun_id,))
        if not conn.execute("SELECT 1 FROM akun WHERE aktif = 1 AND jenis = 'tunai'").fetchone():
            conn.rollback()
            flash("Minimal harus ada satu akun kas tunai yang aktif.", "galat")
            return redirect(url_for("pengaturan.index") + "#akun")
    else:
        nama = request.form.get("nama", "").strip()
        if not nama:
            flash("Nama akun tidak boleh kosong.", "galat")
            return redirect(url_for("pengaturan.index") + "#akun")
        try:
            conn.execute("UPDATE akun SET nama = ? WHERE id = ?", (nama, akun_id))
        except sqlite3.IntegrityError:
            flash(f"Akun {nama} sudah ada.", "galat")
            return redirect(url_for("pengaturan.index") + "#akun")
    conn.commit()
    flash("Akun diperbarui.", "sukses")
    return redirect(url_for("pengaturan.index") + "#akun")


@bp.post("/kategori")
def tambah_kategori():
    conn = get_db()
    nama = request.form.get("nama", "").strip()
    if nama:
        conn.execute("INSERT OR IGNORE INTO kategori_biaya (nama) VALUES (?)", (nama,))
        conn.commit()
        flash(f"Kategori {nama} ditambahkan.", "sukses")
    return redirect(url_for("pengaturan.index") + "#kategori")


@bp.post("/kategori/<int:kategori_id>/hapus")
def hapus_kategori(kategori_id):
    conn = get_db()
    row = conn.execute("SELECT nama FROM kategori_biaya WHERE id = ?", (kategori_id,)).fetchone()
    if row and row["nama"] != KATEGORI_ADMIN:
        conn.execute("DELETE FROM kategori_biaya WHERE id = ?", (kategori_id,))
        conn.commit()
        flash(f"Kategori {row['nama']} dihapus. Biaya lama dengan kategori ini tetap tersimpan.", "sukses")
    return redirect(url_for("pengaturan.index") + "#kategori")


@bp.get("/backup")
def backup():
    """Salinan utuh database (aman walau aplikasi sedang dipakai) untuk diunduh."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    tujuan = sqlite3.connect(path)
    try:
        get_db().backup(tujuan)
    finally:
        tujuan.close()

    @after_this_request
    def bersihkan(resp):
        resp.call_on_close(lambda: os.path.exists(path) and os.remove(path))
        return resp

    nama = f"usaha-baru-backup-{datetime.now():%Y%m%d-%H%M}.db"
    return send_file(path, as_attachment=True, download_name=nama, mimetype="application/x-sqlite3")
