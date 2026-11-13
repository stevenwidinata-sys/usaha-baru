"""Penjualan: daftar per bulan, form multi-barang dengan metode bayar, detail, edit, hapus."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import services, util
from ..db import get_db
from ..inventory import StokTidakCukup, posisi_stok
from ._bantu import bulan_dari_request, daftar_akun, items_dari_form, tanggal_dari_form

bp = Blueprint("penjualan", __name__, url_prefix="/penjualan")

SQL_DAFTAR = """
    SELECT p.*, a.nama AS akun,
           (SELECT COALESCE(SUM(qty * harga_jual), 0) FROM penjualan_item WHERE penjualan_id = p.id) AS subtotal,
           (SELECT COALESCE(SUM(qty * hpp_satuan), 0) FROM penjualan_item WHERE penjualan_id = p.id) AS hpp,
           (SELECT COALESCE(SUM(qty), 0) FROM penjualan_item WHERE penjualan_id = p.id) AS jumlah_barang
    FROM penjualan p JOIN akun a ON a.id = p.akun_id
"""


def _lengkapi(row):
    d = dict(row)
    d["total"] = d["subtotal"] - d["diskon"]
    d["laba_kotor"] = d["total"] - d["hpp"]
    return d


@bp.get("")
def daftar():
    conn = get_db()
    bulan = bulan_dari_request()
    mulai, sampai = util.periode_bulan(bulan)
    rows = [
        _lengkapi(r)
        for r in conn.execute(SQL_DAFTAR + " WHERE p.tanggal BETWEEN ? AND ? ORDER BY p.tanggal DESC, p.id DESC",
                              (mulai, sampai))
    ]
    per_metode = {}
    for r in rows:
        per_metode[r["metode_bayar"]] = per_metode.get(r["metode_bayar"], 0) + r["total"]
    return render_template(
        "penjualan/daftar.html",
        rows=rows,
        bulan=bulan,
        pilihan_bulan=util.daftar_bulan(),
        total=sum(r["total"] for r in rows),
        laba_kotor=sum(r["laba_kotor"] for r in rows),
        per_metode=per_metode,
    )


def _konteks_form(conn, data, items, penjualan=None):
    barang = posisi_stok(conn)
    milik = {}
    if penjualan:
        for r in conn.execute("SELECT barang_id, qty FROM penjualan_item WHERE penjualan_id = ?", (penjualan["id"],)):
            milik[r["barang_id"]] = milik.get(r["barang_id"], 0) + r["qty"]
    dipakai = {it["barang_id"] for it in items}
    pilihan = []
    for b in barang:
        if not b["aktif"] and b["id"] not in dipakai:
            continue
        pilihan.append({**b, "tersedia": b["stok"] + milik.get(b["id"], 0)})
    akun = daftar_akun(conn)
    return {
        "data": data,
        "items": items or [{"barang_id": None, "qty": 1, "harga": ""}],
        "barang": pilihan,
        "akun_tunai": [a for a in akun if a["jenis"] == "tunai"],
        "akun_nontunai": [a for a in akun if a["jenis"] != "tunai"],
        "metode_bayar": util.METODE_BAYAR,
        "penjualan": penjualan,
        "no_nota": penjualan["no_nota"] if penjualan else services.nomor_nota_berikut(conn),
    }


def _data_dari_form(form):
    metode = form.get("metode_bayar", "tunai")
    if metode not in util.METODE_BAYAR:
        metode = "tunai"
    akun_field = "akun_tunai" if metode == "tunai" else "akun_nontunai"
    return {
        "tanggal": tanggal_dari_form(),
        "pelanggan": form.get("pelanggan", "").strip() or None,
        "diskon": util.parse_int(form.get("diskon"), 0),
        "metode_bayar": metode,
        "akun_id": util.parse_int(form.get(akun_field)),
        "no_referensi": form.get("no_referensi", "").strip() or None,
        "biaya_admin": util.parse_int(form.get("biaya_admin"), 0),
        "catatan": form.get("catatan", "").strip() or None,
    }


def _simpan(penjualan=None):
    conn = get_db()
    data = _data_dari_form(request.form)
    items, galat = items_dari_form(request.form)
    try:
        if galat:
            raise services.InputTidakValid(galat[0])
        if not data["tanggal"]:
            raise services.InputTidakValid("Tanggal tidak valid.")
        if not data["akun_id"]:
            raise services.InputTidakValid("Pilih akun tujuan pembayaran.")
        pid = services.simpan_penjualan(conn, data, items, penjualan["id"] if penjualan else None)
        conn.commit()
    except (services.InputTidakValid, StokTidakCukup) as e:
        conn.rollback()
        flash(str(e), "galat")
        return render_template("penjualan/form.html", **_konteks_form(conn, data, items, penjualan))
    nota = conn.execute("SELECT no_nota FROM penjualan WHERE id = ?", (pid,)).fetchone()["no_nota"]
    flash(f"Penjualan {nota} {'diperbarui' if penjualan else 'disimpan'}.", "sukses")
    if request.form.get("lanjut") == "1":
        return redirect(url_for("penjualan.baru"))
    return redirect(url_for("penjualan.detail", penjualan_id=pid))


@bp.route("/baru", methods=["GET", "POST"])
def baru():
    if request.method == "POST":
        return _simpan()
    conn = get_db()
    data = {"tanggal": util.hari_ini(), "metode_bayar": "tunai", "diskon": 0}
    return render_template("penjualan/form.html", **_konteks_form(conn, data, []))


def _ambil(conn, penjualan_id):
    row = conn.execute(SQL_DAFTAR + " WHERE p.id = ?", (penjualan_id,)).fetchone()
    if row is None:
        abort(404)
    return _lengkapi(row)


@bp.route("/<int:penjualan_id>/edit", methods=["GET", "POST"])
def edit(penjualan_id):
    conn = get_db()
    pj = _ambil(conn, penjualan_id)
    if request.method == "POST":
        return _simpan(pj)
    items = [
        {"barang_id": r["barang_id"], "qty": r["qty"], "harga": r["harga_jual"]}
        for r in conn.execute("SELECT * FROM penjualan_item WHERE penjualan_id = ? ORDER BY id", (penjualan_id,))
    ]
    return render_template("penjualan/form.html", **_konteks_form(conn, pj, items, pj))


@bp.get("/<int:penjualan_id>")
def detail(penjualan_id):
    conn = get_db()
    pj = _ambil(conn, penjualan_id)
    items = conn.execute(
        "SELECT i.*, b.nama, b.kode, b.satuan FROM penjualan_item i JOIN barang b ON b.id = i.barang_id "
        "WHERE i.penjualan_id = ? ORDER BY i.id",
        (penjualan_id,),
    ).fetchall()
    return render_template("penjualan/detail.html", pj=pj, items=items)


@bp.post("/<int:penjualan_id>/hapus")
def hapus(penjualan_id):
    conn = get_db()
    pj = _ambil(conn, penjualan_id)
    services.hapus_penjualan(conn, penjualan_id)
    conn.commit()
    flash(f"Penjualan {pj['no_nota']} dihapus.", "sukses")
    return redirect(url_for("penjualan.daftar", bulan=pj["tanggal"][:7]))
