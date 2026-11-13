"""Pembelian barang: daftar per bulan, form multi-barang, detail, edit, hapus."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import reports, services, util
from ..db import get_db
from ..inventory import StokTidakCukup, posisi_stok
from ._bantu import bulan_dari_request, daftar_akun, items_dari_form, tanggal_dari_form

bp = Blueprint("pembelian", __name__, url_prefix="/pembelian")

SQL_DAFTAR = """
    SELECT p.*, a.nama AS akun,
           (SELECT COALESCE(SUM(qty * harga_beli), 0) FROM pembelian_item WHERE pembelian_id = p.id) AS total,
           (SELECT COUNT(*) FROM pembelian_item WHERE pembelian_id = p.id) AS jumlah_baris,
           (SELECT COALESCE(SUM(jumlah), 0) FROM pembayaran_hutang WHERE pembelian_id = p.id) AS terbayar
    FROM pembelian p JOIN akun a ON a.id = p.akun_id
"""


def _lengkapi(row):
    d = dict(row)
    d["nomor"] = d["no_faktur"] or f"PB-{d['id']:04d}"
    d["sisa"] = d["total"] - d["uang_muka"] - d["terbayar"] if d["cara_bayar"] == "tempo" else 0
    return d


@bp.get("")
def daftar():
    conn = get_db()
    bulan = bulan_dari_request()
    mulai, sampai = util.periode_bulan(bulan)
    rows = [
        _lengkapi(r)
        for r in conn.execute(
            SQL_DAFTAR + " WHERE p.tanggal BETWEEN ? AND ? ORDER BY p.tanggal DESC, p.id DESC", (mulai, sampai)
        )
    ]
    hutang = reports.ringkasan_hutang(reports.daftar_hutang(conn))
    return render_template(
        "pembelian/daftar.html",
        rows=rows,
        bulan=bulan,
        pilihan_bulan=util.daftar_bulan(),
        total=sum(r["total"] for r in rows),
        total_tempo=sum(r["total"] for r in rows if r["cara_bayar"] == "tempo"),
        hutang=hutang,
        hari_ini=util.hari_ini(),
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
        "cara_bayar": "tempo" if f.get("cara_bayar") == "tempo" else "lunas",
        "jatuh_tempo": util.parse_tanggal(f.get("jatuh_tempo", "")),
        "uang_muka": util.parse_int(f.get("uang_muka"), 0),
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
    pesan = "Stok dan harga modal sudah diperbarui."
    if data["cara_bayar"] == "tempo":
        pesan += f" Hutang tercatat, jatuh tempo {util.tanggal(data['jatuh_tempo'])}."
    flash(f"Pembelian {'diperbarui' if pembelian else 'disimpan'}. {pesan}", "sukses")
    return redirect(url_for("pembelian.detail", pembelian_id=pid))


def _ambil(conn, pembelian_id):
    row = conn.execute(SQL_DAFTAR + " WHERE p.id = ?", (pembelian_id,)).fetchone()
    if row is None:
        abort(404)
    return _lengkapi(row)


@bp.route("/baru", methods=["GET", "POST"])
def baru():
    if request.method == "POST":
        return _simpan()
    conn = get_db()
    data = {"tanggal": util.hari_ini(), "cara_bayar": "lunas"}
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
    pembayaran = conn.execute(
        "SELECT h.*, a.nama AS akun FROM pembayaran_hutang h JOIN akun a ON a.id = h.akun_id "
        "WHERE h.pembelian_id = ? ORDER BY h.tanggal, h.id",
        (pembelian_id,),
    ).fetchall()
    status = None
    if pb["cara_bayar"] == "tempo":
        status = next(
            (h for h in reports.daftar_hutang(conn, termasuk_lunas=True) if h["id"] == pembelian_id), None
        )
    return render_template(
        "pembelian/detail.html", pb=pb, items=items, pembayaran=pembayaran, status=status,
        akun=daftar_akun(conn), hari_ini=util.hari_ini(),
    )


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
