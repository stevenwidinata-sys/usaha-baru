"""Daftar barang, tambah/edit barang, dan kartu stok."""
import sqlite3

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import services, util
from ..db import get_db
from ..inventory import kartu_stok, posisi_stok
from ._bantu import bulan_dari_request

bp = Blueprint("barang", __name__, url_prefix="/barang")


def _kode_berikut(conn):
    n = conn.execute(
        "SELECT MAX(CAST(SUBSTR(kode, 5) AS INTEGER)) FROM barang WHERE kode LIKE 'BRG-%'"
    ).fetchone()[0]
    return f"BRG-{(n or 0) + 1:03d}"


@bp.get("")
def daftar():
    conn = get_db()
    q = request.args.get("q", "").strip().lower()
    filter_ = request.args.get("f", "semua")
    tampil_nonaktif = request.args.get("nonaktif") == "1"

    semua = posisi_stok(conn, hanya_aktif=not tampil_nonaktif)
    aktif = [b for b in semua if b["aktif"]]
    perlu_isi = [b for b in aktif if b["status"] != "aman"]

    barang = semua
    if filter_ == "isi":
        barang = [b for b in barang if b["aktif"] and b["status"] != "aman"]
    if q:
        barang = [b for b in barang if q in b["nama"].lower() or q in b["kode"].lower()]

    return render_template(
        "barang/daftar.html",
        barang=barang,
        jumlah_aktif=len(aktif),
        jumlah_perlu_isi=len(perlu_isi),
        total_nilai=sum(b["nilai"] for b in aktif),
        total_tampil=sum(b["nilai"] for b in barang),
        q=request.args.get("q", ""),
        filter_=filter_,
        tampil_nonaktif=tampil_nonaktif,
    )


def _data_form():
    f = request.form
    return {
        "kode": f.get("kode", "").strip(),
        "nama": f.get("nama", "").strip(),
        "satuan": f.get("satuan", "").strip() or "pcs",
        "harga_jual": util.parse_int(f.get("harga_jual"), 0),
        "stok_minimum": util.parse_int(f.get("stok_minimum"), 0),
    }


def _validasi(data):
    if not data["kode"] or not data["nama"]:
        return "Kode dan nama barang wajib diisi."
    if data["harga_jual"] < 0 or data["stok_minimum"] < 0:
        return "Harga jual dan stok minimum tidak boleh negatif."
    return None


@bp.route("/baru", methods=["GET", "POST"])
def baru():
    conn = get_db()
    if request.method == "POST":
        data = _data_form()
        galat = _validasi(data)
        stok_awal = util.parse_int(request.form.get("stok_awal"), 0)
        modal_awal = util.parse_int(request.form.get("modal_awal"))
        tgl_awal = util.parse_tanggal(request.form.get("tanggal_awal", "")) or util.hari_ini()
        if not galat and stok_awal and modal_awal is None:
            galat = "Isi harga modal per satuan untuk stok awal."
        if not galat:
            try:
                bid = conn.execute(
                    "INSERT INTO barang (kode, nama, satuan, harga_jual, stok_minimum) VALUES (?, ?, ?, ?, ?)",
                    (data["kode"], data["nama"], data["satuan"], data["harga_jual"], data["stok_minimum"]),
                ).lastrowid
                if stok_awal:
                    services.simpan_stok_awal(conn, tgl_awal, bid, stok_awal, modal_awal)
                conn.commit()
                flash(f"Barang {data['nama']} ditambahkan.", "sukses")
                return redirect(url_for("barang.daftar"))
            except sqlite3.IntegrityError:
                conn.rollback()
                galat = f"Kode {data['kode']} sudah dipakai barang lain."
            except services.InputTidakValid as e:
                conn.rollback()
                galat = str(e)
        flash(galat, "galat")
        return render_template("barang/form.html", data=request.form, baru=True, hari_ini=util.hari_ini())
    return render_template(
        "barang/form.html",
        data={"kode": _kode_berikut(conn), "satuan": "pcs"},
        baru=True,
        hari_ini=util.hari_ini(),
    )


@bp.route("/<int:barang_id>/edit", methods=["GET", "POST"])
def edit(barang_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM barang WHERE id = ?", (barang_id,)).fetchone() or abort(404)
    if request.method == "POST":
        data = _data_form()
        galat = _validasi(data)
        if not galat:
            try:
                conn.execute(
                    "UPDATE barang SET kode = ?, nama = ?, satuan = ?, harga_jual = ?, stok_minimum = ? WHERE id = ?",
                    (data["kode"], data["nama"], data["satuan"], data["harga_jual"], data["stok_minimum"], barang_id),
                )
                conn.commit()
                flash("Data barang diperbarui.", "sukses")
                return redirect(url_for("barang.daftar"))
            except sqlite3.IntegrityError:
                conn.rollback()
                galat = f"Kode {data['kode']} sudah dipakai barang lain."
        flash(galat, "galat")
        return render_template("barang/form.html", data=request.form, baru=False, barang=row)
    return render_template("barang/form.html", data=row, baru=False, barang=row)


@bp.post("/<int:barang_id>/aktif")
def ubah_aktif(barang_id):
    conn = get_db()
    row = conn.execute("SELECT nama, aktif FROM barang WHERE id = ?", (barang_id,)).fetchone() or abort(404)
    conn.execute("UPDATE barang SET aktif = ? WHERE id = ?", (0 if row["aktif"] else 1, barang_id))
    conn.commit()
    flash(f"{row['nama']} {'dinonaktifkan' if row['aktif'] else 'diaktifkan kembali'}.", "sukses")
    return redirect(request.referrer or url_for("barang.daftar"))


@bp.post("/<int:barang_id>/hapus")
def hapus(barang_id):
    conn = get_db()
    row = conn.execute("SELECT nama FROM barang WHERE id = ?", (barang_id,)).fetchone() or abort(404)
    if conn.execute("SELECT 1 FROM mutasi_stok WHERE barang_id = ? LIMIT 1", (barang_id,)).fetchone():
        flash("Barang yang sudah punya transaksi tidak bisa dihapus. Nonaktifkan saja.", "galat")
        return redirect(url_for("barang.daftar"))
    conn.execute("DELETE FROM barang WHERE id = ?", (barang_id,))
    conn.commit()
    flash(f"{row['nama']} dihapus.", "sukses")
    return redirect(url_for("barang.daftar"))


@bp.get("/<int:barang_id>")
def kartu(barang_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM barang WHERE id = ?", (barang_id,)).fetchone() or abort(404)
    bulan = bulan_dari_request()
    mulai, sampai = util.periode_bulan(bulan)
    data = kartu_stok(conn, barang_id, mulai, sampai)
    stok = next((b for b in posisi_stok(conn) if b["id"] == barang_id), None)
    return render_template(
        "barang/kartu.html",
        barang=row,
        stok=stok,
        kartu=data,
        bulan=bulan,
        pilihan_bulan=util.daftar_bulan(),
        semua_barang=conn.execute("SELECT id, nama FROM barang ORDER BY nama").fetchall(),
    )
