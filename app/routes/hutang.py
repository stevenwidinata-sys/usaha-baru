"""Hutang pemasok dari pembelian tempo: daftar, pembayaran (boleh dicicil), dan hapus pembayaran."""
from flask import Blueprint, flash, redirect, render_template, request, url_for

from .. import reports, services, util
from ..db import get_db
from ._bantu import akun_valid, daftar_akun, tanggal_dari_form

bp = Blueprint("hutang", __name__, url_prefix="/hutang")


@bp.get("")
def daftar():
    conn = get_db()
    semua = request.args.get("semua") == "1"
    hutang = reports.daftar_hutang(conn, termasuk_lunas=semua)
    belum = [h for h in hutang if h["sisa"] > 0]
    pilih_id = util.parse_int(request.args.get("pilih"))
    pilihan = next((h for h in belum if h["id"] == pilih_id), belum[0] if belum else None)
    riwayat = []
    if pilihan:
        riwayat = conn.execute(
            "SELECT h.*, a.nama AS akun FROM pembayaran_hutang h JOIN akun a ON a.id = h.akun_id "
            "WHERE h.pembelian_id = ? ORDER BY h.tanggal, h.id",
            (pilihan["id"],),
        ).fetchall()
        dp = conn.execute(
            "SELECT p.uang_muka, p.tanggal, a.nama AS akun FROM pembelian p JOIN akun a ON a.id = p.akun_id "
            "WHERE p.id = ?",
            (pilihan["id"],),
        ).fetchone()
        pilihan = {**pilihan, "dp": dp}
    hari_ini = util.hari_ini()
    return render_template(
        "hutang.html",
        hutang=hutang,
        ringkasan=reports.ringkasan_hutang(hutang),
        pilihan=pilihan,
        riwayat=riwayat,
        akun=daftar_akun(conn),
        semua=semua,
        hari_ini=hari_ini,
    )


@bp.post("/<int:pembelian_id>/bayar")
def bayar(pembelian_id):
    conn = get_db()
    tanggal = tanggal_dari_form()
    jumlah = util.parse_int(request.form.get("jumlah"))
    akun_id = util.parse_int(request.form.get("akun_id"))
    try:
        if not akun_valid(conn, akun_id):
            raise services.InputTidakValid("Pilih akun yang dipakai membayar.")
        services.bayar_hutang(conn, pembelian_id, tanggal, jumlah, akun_id,
                              request.form.get("keterangan", "").strip() or None)
        conn.commit()
        sisa = services.sisa_hutang(conn, pembelian_id)
        flash(f"Pembayaran {util.rupiah(jumlah)} dicatat. "
              + ("Hutang lunas." if sisa <= 0 else f"Sisa hutang {util.rupiah(sisa)}."), "sukses")
    except services.InputTidakValid as e:
        conn.rollback()
        flash(str(e), "galat")
    if request.form.get("kembali") == "pembelian":
        return redirect(url_for("pembelian.detail", pembelian_id=pembelian_id))
    return redirect(url_for("hutang.daftar", pilih=pembelian_id))


@bp.post("/pembayaran/<int:pembayaran_id>/hapus")
def hapus_pembayaran(pembayaran_id):
    conn = get_db()
    pembelian_id = services.hapus_pembayaran_hutang(conn, pembayaran_id)
    conn.commit()
    flash("Pembayaran hutang dihapus.", "sukses")
    if pembelian_id:
        return redirect(request.referrer or url_for("pembelian.detail", pembelian_id=pembelian_id))
    return redirect(url_for("hutang.daftar"))


def jumlah_hutang_telat(conn):
    """Untuk lencana di menu samping."""
    return reports.ringkasan_hutang(reports.daftar_hutang(conn))["telat"]["faktur"]
