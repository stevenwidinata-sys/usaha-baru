"""Stok awal dan stok opname (penyesuaian stok)."""
from flask import Blueprint, flash, redirect, render_template, request, url_for

from .. import services, util
from ..db import get_db
from ..inventory import StokTidakCukup, posisi_stok
from ._bantu import tanggal_dari_form

bp = Blueprint("stok", __name__, url_prefix="/stok")


@bp.get("")
def daftar():
    conn = get_db()
    riwayat = conn.execute(
        "SELECT ps.*, b.nama, b.satuan, "
        "(SELECT harga FROM mutasi_stok m WHERE m.sumber = ps.jenis AND m.ref_id = ps.id) AS harga_mutasi "
        "FROM penyesuaian_stok ps JOIN barang b ON b.id = ps.barang_id "
        "ORDER BY ps.tanggal DESC, ps.id DESC LIMIT 200"
    ).fetchall()
    return render_template(
        "stok/penyesuaian.html",
        riwayat=riwayat,
        barang=posisi_stok(conn, hanya_aktif=True),
        hari_ini=util.hari_ini(),
        jenis=request.args.get("jenis", "opname"),
    )


@bp.post("")
def simpan():
    conn = get_db()
    f = request.form
    jenis = f.get("jenis")
    tanggal = tanggal_dari_form()
    barang_id = util.parse_int(f.get("barang_id"))
    alasan = f.get("alasan", "").strip() or None
    try:
        if not tanggal or not barang_id:
            raise services.InputTidakValid("Pilih barang dan tanggal.")
        if jenis == "stok_awal":
            services.simpan_stok_awal(
                conn, tanggal, barang_id, util.parse_int(f.get("qty"), 0), util.parse_int(f.get("nilai_satuan")), alasan
            )
        else:
            services.simpan_opname(conn, tanggal, barang_id, util.parse_int(f.get("stok_fisik")), alasan)
        conn.commit()
        flash("Penyesuaian stok disimpan.", "sukses")
    except (services.InputTidakValid, StokTidakCukup) as e:
        conn.rollback()
        flash(str(e), "galat")
    return redirect(url_for("stok.daftar", jenis=jenis))


@bp.post("/<int:penyesuaian_id>/hapus")
def hapus(penyesuaian_id):
    conn = get_db()
    try:
        services.hapus_penyesuaian(conn, penyesuaian_id)
        conn.commit()
        flash("Penyesuaian stok dihapus.", "sukses")
    except StokTidakCukup as e:
        conn.rollback()
        flash(f"Tidak bisa dihapus. {e}", "galat")
    return redirect(url_for("stok.daftar"))
