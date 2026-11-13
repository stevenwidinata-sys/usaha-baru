"""Fungsi bantu bersama untuk halaman."""
import csv
import io

from flask import Response, request

from .. import util


def daftar_akun(conn, hanya_aktif=True):
    sql = "SELECT * FROM akun" + (" WHERE aktif = 1" if hanya_aktif else "") + " ORDER BY id"
    return conn.execute(sql).fetchall()


def akun_valid(conn, akun_id):
    return akun_id is not None and conn.execute(
        "SELECT 1 FROM akun WHERE id = ?", (akun_id,)
    ).fetchone() is not None


def bulan_dari_request(nama="bulan"):
    ym = request.args.get(nama, "")
    return ym if util.valid_bulan(ym) else util.bulan_ini()


def tahun_dari_request():
    th = util.parse_int(request.args.get("tahun"))
    return th if th and 1900 <= th <= 9999 else int(util.bulan_ini()[:4])


def tanggal_dari_form(nama="tanggal"):
    return util.parse_tanggal(request.form.get(nama, ""))


def items_dari_form(form):
    """Baca baris barang dari form (barang_id[], qty[], harga[]). Baris kosong diabaikan."""
    items, galat = [], []
    for bid, qty, harga in zip(form.getlist("barang_id"), form.getlist("qty"), form.getlist("harga")):
        if not bid:
            continue
        b, q, h = util.parse_int(bid), util.parse_int(qty), util.parse_int(harga)
        if b is None or q is None or h is None:
            galat.append("Periksa kembali jumlah dan harga setiap barang.")
            continue
        items.append({"barang_id": b, "qty": q, "harga": h})
    return items, galat


def respons_csv(nama_file, header, baris):
    """CSV dengan pemisah titik koma + BOM supaya rapi saat dibuka di Excel versi Indonesia."""
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(header)
    w.writerows(baris)
    return Response(
        "﻿" + buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{nama_file}"'},
    )
