"""Halaman laporan: laba rugi (bulanan/tahunan), arus kas, neraca. Bisa dicetak dan diunduh CSV."""
from flask import Blueprint, render_template, request

from .. import reports, util
from ..db import get_db
from ._bantu import bulan_dari_request, respons_csv, tahun_dari_request

bp = Blueprint("laporan", __name__, url_prefix="/laporan")


def _pilihan_tahun(conn):
    sekarang = int(util.bulan_ini()[:4])
    awal = conn.execute(
        "SELECT MIN(tanggal) FROM (SELECT MIN(tanggal) AS tanggal FROM penjualan UNION ALL "
        "SELECT MIN(tanggal) FROM pembelian UNION ALL SELECT MIN(tanggal) FROM transaksi_modal UNION ALL "
        "SELECT MIN(tanggal) FROM penyesuaian_stok)"
    ).fetchone()[0]
    awal = min(int(awal[:4]), sekarang) if awal else sekarang
    return list(range(sekarang, awal - 1, -1))


def _csv_laba_rugi(lr, judul):
    baris = [
        ["Penjualan kotor", lr["penjualan_kotor"]],
        ["Diskon penjualan", -lr["diskon"]],
        ["Penjualan bersih", lr["penjualan_bersih"]],
        ["Harga pokok penjualan (HPP)", -lr["hpp"]],
        ["Laba kotor", lr["laba_kotor"]],
        *[[f"Biaya: {k}", -v] for k, v in lr["biaya"]],
        ["Total biaya operasional", -lr["total_biaya"]],
        ["Selisih stok opname", lr["selisih_stok"]],
        ["Laba bersih", lr["laba_bersih"]],
    ]
    return respons_csv(f"laba-rugi-{judul}.csv", ["Pos", "Jumlah (Rp)"], baris)


@bp.get("/laba-rugi")
def laba_rugi():
    conn = get_db()
    mode = "tahunan" if request.args.get("mode") == "tahunan" else "bulanan"
    csv = request.args.get("format") == "csv"
    if mode == "tahunan":
        tahun = tahun_dari_request()
        data = reports.laba_rugi_tahunan(conn, tahun)
        if csv:
            kolom = ["Bulan", "Penjualan bersih", "HPP", "Laba kotor", "Biaya operasional", "Selisih stok", "Laba bersih"]
            baris = [
                [b["nama"], b["penjualan_bersih"], b["hpp"], b["laba_kotor"], b["total_biaya"], b["selisih_stok"],
                 b["laba_bersih"]]
                for b in data["bulan"] + [{**data["total"], "nama": "Total"}]
            ]
            return respons_csv(f"laba-rugi-{tahun}.csv", kolom, baris)
        aktif = [b for b in data["bulan"] if b["transaksi"] or b["total_biaya"]]
        maks = max([abs(b["laba_bersih"]) for b in data["bulan"]] + [1])
        return render_template(
            "laporan/laba_rugi.html", mode=mode, tahun=tahun, data=data, pilihan_tahun=_pilihan_tahun(conn),
            maks=maks, bulan_aktif=len(aktif),
        )

    bulan = bulan_dari_request()
    lr = reports.laba_rugi_bulan(conn, bulan)
    if csv:
        return _csv_laba_rugi(lr, bulan)
    lalu = reports.laba_rugi_bulan(conn, util.geser_bulan(bulan, -1))
    return render_template(
        "laporan/laba_rugi.html", mode=mode, bulan=bulan, lr=lr, lalu=lalu, pilihan_bulan=util.daftar_bulan(),
        pilihan_tahun=_pilihan_tahun(conn), perubahan=reports.perubahan,
    )


@bp.get("/arus-kas")
def arus_kas():
    conn = get_db()
    mode = "tahunan" if request.args.get("mode") == "tahunan" else "bulanan"
    if mode == "tahunan":
        tahun = tahun_dari_request()
        mulai, sampai, judul = f"{tahun}-01-01", f"{tahun}-12-31", f"Tahun {tahun}"
        nama_file = str(tahun)
    else:
        bulan = bulan_dari_request()
        mulai, sampai = util.periode_bulan(bulan)
        judul, nama_file = util.label_bulan(bulan), bulan
    data = reports.arus_kas(conn, mulai, sampai)
    if request.args.get("format") == "csv":
        baris = [["Saldo awal", data["saldo_awal"]]]
        baris += [[f"Masuk: {k}", v] for k, v in data["masuk"]]
        baris += [[f"Keluar: {k}", -v] for k, v in data["keluar"]]
        baris += [["Arus kas bersih", data["bersih"]], ["Saldo akhir", data["saldo_akhir"]]]
        baris += [[f"Saldo {a['nama']}", a["saldo"]] for a in data["per_akun"]]
        return respons_csv(f"arus-kas-{nama_file}.csv", ["Pos", "Jumlah (Rp)"], baris)
    return render_template(
        "laporan/arus_kas.html", mode=mode, data=data, judul=judul,
        bulan=request.args.get("bulan") if mode == "bulanan" else None,
        bulan_dipilih=bulan_dari_request(), tahun=tahun_dari_request(),
        pilihan_bulan=util.daftar_bulan(), pilihan_tahun=_pilihan_tahun(conn),
    )


@bp.get("/neraca")
def neraca():
    conn = get_db()
    per = util.parse_tanggal(request.args.get("tanggal", "")) or util.hari_ini()
    data = reports.neraca(conn, per)
    if request.args.get("format") == "csv":
        baris = [[f"Aset: {a['nama']}", a["saldo"]] for a in data["akun"]]
        baris += [
            ["Aset: Persediaan barang", data["persediaan"]],
            ["Total aset", data["total_aset"]],
            ["Modal: Setoran uang", data["setoran"]],
            ["Modal: Stok awal", data["stok_awal"]],
            ["Modal: Laba tahun-tahun sebelumnya", data["laba_lalu"]],
            ["Modal: Laba tahun berjalan", data["laba_berjalan"]],
            ["Modal: Prive", -data["prive"]],
            ["Total modal", data["total_modal"]],
        ]
        return respons_csv(f"neraca-{per}.csv", ["Pos", "Jumlah (Rp)"], baris)
    return render_template("laporan/neraca.html", data=data, per=per)
