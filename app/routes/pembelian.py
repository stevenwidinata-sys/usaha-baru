"""Pembelian barang: daftar per bulan, form multi-barang, detail, edit, hapus."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import services, util
from ..db import get_db
from ..inventory import StokTidakCukup, posisi_stok
from ._bantu import bulan_dari_request, daftar_akun, items_dari_form, tanggal_dari_form

bp = Blueprint("pembelian", __name__, url_prefix="/pembelian")

SQL_DAFTAR = """
    SELECT p.*, a.nama AS akun,
           (SELECT COALESCE(SUM(qty * harga_beli), 0) FROM pembelian_item WHERE pembelian_id = p.id) AS total,
           (SELECT COUNT(*) FROM pembelian_item WHERE pembelian_id = p.id) AS jumlah_baris
    FROM pembelian p JOIN akun a ON a.id = p.akun_id
"""


@bp.get("")
def daftar():
    conn = get_db()
    bulan = bulan_dari_request()
    mulai, sampai = util.periode_bulan(bulan)
    rows = conn.execute(
        SQL_DAFTAR + " WHERE p.tanggal BETWEEN ? AND ? ORDER BY p.tanggal DESC, p.id DESC", (mulai, sampai)
    ).fetchall()
    return render_template(
        "pembelian/daftar.html",
        rows=rows,
        bulan=bulan,
        pilihan_bulan=util.daftar_bulan(),
        total=sum(r["total"] for r in rows),
    )


def _harga_beli_terakhir(conn):
    return {
        r["barang_id"]: r["harga_beli"]
        for r in conn.execute(
            "SELECT i.barang_id, i.harga_beli FROM pembelian_item i JOIN pembelian p ON p.id = i.pembelian_id "
            "ORDER BY p.tanggal, i.id"
        )
    }


def _konteks_form(conn, data, items, pembelian=None):
    terakhir = _harga_beli_terakhir(conn)
    dipakai = {it["barang_id"] for it in items}
    barang = [
        {**b, "harga_beli": terakhir.get(b["id"], round(b["hpp"]))}
        for b in posisi_stok(conn)
        if b["aktif"] or b["id"] in dipakai
    ]
    return {
        "data": data,
        "items": items or [{"barang_id": None, "qty": 1, "harga": ""}],
        "barang": barang,
        "akun": daftar_akun(conn),
        "pembelian": pembelian,
    }


def _simpan(pembelian=None):
    conn = get_db()
    f = request.form
    data = {
        "tanggal": tanggal_dari_form(),
        "no_faktur": f.get("no_faktur", "").strip() or None,
        "pemasok": f.get("pemasok", "").strip() or None,
        "akun_id": util.parse_int(f.get("akun_id")),
        "catatan": f.get("catatan", "").strip() or None,
    }
    items, galat = items_dari_form(f)
    try:
        if galat:
            raise services.InputTidakValid(galat[0])
        if not data["tanggal"]:
            raise services.InputTidakValid("Tanggal tidak valid.")
        if not data["akun_id"]:
            raise services.InputTidakValid("Pilih akun yang dipakai membayar.")
        pid = services.simpan_pembelian(conn, data, items, pembelian["id"] if pembelian else None)
        conn.commit()
    except (services.InputTidakValid, StokTidakCukup) as e:
        conn.rollback()
        flash(str(e), "galat")
        return render_template("pembelian/form.html", **_konteks_form(conn, data, items, pembelian))
    flash(f"Pembelian {'diperbarui' if pembelian else 'disimpan'}. Stok dan harga modal sudah diperbarui.", "sukses")
    return redirect(url_for("pembelian.detail", pembelian_id=pid))


def _ambil(conn, pembelian_id):
    row = conn.execute(SQL_DAFTAR + " WHERE p.id = ?", (pembelian_id,)).fetchone()
    if row is None:
        abort(404)
    return row


@bp.route("/baru", methods=["GET", "POST"])
def baru():
    if request.method == "POST":
        return _simpan()
    conn = get_db()
    data = {"tanggal": util.hari_ini()}
    return render_template("pembelian/form.html", **_konteks_form(conn, data, []))


@bp.route("/<int:pembelian_id>/edit", methods=["GET", "POST"])
def edit(pembelian_id):
    conn = get_db()
    pb = _ambil(conn, pembelian_id)
    if request.method == "POST":
        return _simpan(pb)
    items = [
        {"barang_id": r["barang_id"], "qty": r["qty"], "harga": r["harga_beli"]}
        for r in conn.execute("SELECT * FROM pembelian_item WHERE pembelian_id = ? ORDER BY id", (pembelian_id,))
    ]
    return render_template("pembelian/form.html", **_konteks_form(conn, pb, items, pb))


@bp.get("/<int:pembelian_id>")
def detail(pembelian_id):
    conn = get_db()
    pb = _ambil(conn, pembelian_id)
    items = conn.execute(
        "SELECT i.*, b.nama, b.kode, b.satuan FROM pembelian_item i JOIN barang b ON b.id = i.barang_id "
        "WHERE i.pembelian_id = ? ORDER BY i.id",
        (pembelian_id,),
    ).fetchall()
    return render_template("pembelian/detail.html", pb=pb, items=items)


@bp.post("/<int:pembelian_id>/hapus")
def hapus(pembelian_id):
    conn = get_db()
    pb = _ambil(conn, pembelian_id)
    try:
        services.hapus_pembelian(conn, pembelian_id)
        conn.commit()
        flash("Pembelian dihapus.", "sukses")
        return redirect(url_for("pembelian.daftar", bulan=pb["tanggal"][:7]))
    except StokTidakCukup as e:
        conn.rollback()
        flash(f"Pembelian tidak bisa dihapus karena barangnya sudah terjual. {e}", "galat")
        return redirect(url_for("pembelian.detail", pembelian_id=pembelian_id))
