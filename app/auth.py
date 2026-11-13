"""Login satu pengguna dengan password.

Password disimpan sebagai hash di tabel pengaturan. Bila belum ada password:
- dipakai variabel lingkungan USAHA_PASSWORD (untuk hosting, supaya tidak ada celah sebelum password dibuat), atau
- pengguna diarahkan ke halaman "Buat password" (untuk pemakaian pertama di laptop).
"""
import time
from datetime import timedelta

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .db import ambil_pengaturan, get_db, simpan_pengaturan

bp = Blueprint("auth", __name__)

PANJANG_MINIMAL = 8
BEBAS_LOGIN = {"auth.masuk", "auth.buat_password", "static", "pwa.manifest", "pwa.service_worker"}


def ada_password(conn):
    return bool(ambil_pengaturan(conn, "password_hash", ""))


def set_password(conn, password):
    simpan_pengaturan(conn, "password_hash", generate_password_hash(password))


def _cek_password_baru(password, konfirmasi):
    if len(password) < PANJANG_MINIMAL:
        return f"Password minimal {PANJANG_MINIMAL} karakter."
    if password != konfirmasi:
        return "Konfirmasi password tidak sama."
    return None


def _tujuan_aman(tujuan):
    return tujuan if tujuan and tujuan.startswith("/") and not tujuan.startswith("//") else url_for("dashboard.index")


def _masukkan(ingat):
    session.clear()
    session["masuk"] = True
    session.permanent = ingat


def init_app(app):
    app.permanent_session_lifetime = timedelta(days=30)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)

    @app.before_request
    def wajib_login():
        if current_app.config.get("LOGIN_DISABLED") or request.endpoint in BEBAS_LOGIN or request.endpoint is None:
            return None
        if session.get("masuk"):
            return None
        if not ada_password(get_db()):
            return redirect(url_for("auth.buat_password"))
        tujuan = request.full_path.rstrip("?") if request.method == "GET" else None
        return redirect(url_for("auth.masuk", next=tujuan))


@bp.route("/masuk", methods=["GET", "POST"])
def masuk():
    conn = get_db()
    if not ada_password(conn):
        return redirect(url_for("auth.buat_password"))
    if request.method == "POST":
        hash_ = ambil_pengaturan(conn, "password_hash")
        if check_password_hash(hash_, request.form.get("password", "")):
            _masukkan(ingat=request.form.get("ingat") == "1")
            return redirect(_tujuan_aman(request.args.get("next")))
        time.sleep(1)  # memperlambat tebak-tebakan password
        flash("Password salah.", "galat")
    return render_template("auth/masuk.html")


@bp.route("/buat-password", methods=["GET", "POST"])
def buat_password():
    conn = get_db()
    if ada_password(conn):
        return redirect(url_for("auth.masuk"))
    if request.method == "POST":
        galat = _cek_password_baru(request.form.get("password", ""), request.form.get("konfirmasi", ""))
        if galat:
            flash(galat, "galat")
        else:
            set_password(conn, request.form["password"])
            conn.commit()
            _masukkan(ingat=True)
            flash("Password dibuat. Simpan baik-baik, password ini dipakai setiap kali masuk.", "sukses")
            return redirect(url_for("dashboard.index"))
    return render_template("auth/buat_password.html", minimal=PANJANG_MINIMAL)


@bp.post("/keluar")
def keluar():
    session.clear()
    return redirect(url_for("auth.masuk"))


@bp.post("/pengaturan/password")
def ganti_password():
    conn = get_db()
    lama = request.form.get("lama", "")
    if ada_password(conn) and not check_password_hash(ambil_pengaturan(conn, "password_hash"), lama):
        time.sleep(1)
        flash("Password lama salah.", "galat")
    else:
        galat = _cek_password_baru(request.form.get("password", ""), request.form.get("konfirmasi", ""))
        if galat:
            flash(galat, "galat")
        else:
            set_password(conn, request.form["password"])
            conn.commit()
            flash("Password diganti.", "sukses")
    return redirect(url_for("pengaturan.index") + "#password")
