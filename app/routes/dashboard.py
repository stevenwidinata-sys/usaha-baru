"""Dashboard ringkasan usaha."""
from flask import Blueprint, render_template

from .. import reports, util
from ..db import get_db
from ..inventory import posisi_stok
from ._bantu import bulan_dari_request

bp = Blueprint("dashboard", __name__)

SQL_TERAKHIR = """
    SELECT 'penjualan' AS jenis, p.id, p.tanggal, p.no_nota AS nomor,
           COALESCE(p.pelanggan, 'Pelanggan umum') AS ket, p.metode_bayar AS metode,
           (SELECT COALESCE(SUM(qty * harga_jual), 0) FROM penjualan_item WHERE penjualan_id = p.id) - p.diskon AS jumlah
    FROM penjualan p
    UNION ALL
    SELECT 'pembelian', b.id, b.tanggal, COALESCE(b.no_faktur, printf('PB-%04d', b.id)),
           COALESCE(b.pemasok, 'Pembelian barang'), NULL,
           -(SELECT COALESCE(SUM(qty * harga_beli), 0) FROM pembelian_item WHERE pembelian_id = b.id)
    FROM pembelian b
    UNION ALL
    SELECT 'biaya', id, tanggal, printf('BY-%04d', id), kategori || COALESCE(' · ' || keterangan, ''), NULL, -jumlah
    FROM biaya
    UNION ALL
    SELECT jenis, id, tanggal, printf('MD-%04d', id),
           COALESCE(keterangan, CASE jenis WHEN 'setoran' THEN 'Setoran modal' ELSE 'Ambil untuk pribadi' END), NULL,
           CASE jenis WHEN 'setoran' THEN jumlah ELSE -jumlah END
    FROM transaksi_modal
    ORDER BY tanggal DESC, id DESC
    LIMIT 8
"""


def _grafik(conn, tahun, bulan_ini):
    data = reports.laba_rugi_tahunan(conn, tahun)["bulan"]
    maks = max([abs(b["laba_bersih"]) for b in data] + [1])
    juta = maks >= 1_000_000
    satuan = "juta rupiah" if juta else "ribu rupiah"
    hasil = []
    for i, b in enumerate(data):
        ada = bool(b["transaksi"] or b["total_biaya"] or b["selisih_stok"])
        nilai = b["laba_bersih"] / (1_000_000 if juta else 1_000)
        hasil.append({
            "label": util.BULAN_PENDEK[i],
            "ym": b["ym"],
            "ada": ada,
            "teks": (f"{nilai:.2f}" if juta else f"{nilai:.0f}").replace(".", ",") if ada else "–",
            "tinggi": max(4, round(abs(b["laba_bersih"]) / maks * 160)) if ada else 4,
            "minus": b["laba_bersih"] < 0,
            "ini": b["ym"] == bulan_ini,
        })
    return hasil, satuan


@bp.get("/")
def index():
    conn = get_db()
    bulan = bulan_dari_request()
    mulai, sampai = util.periode_bulan(bulan)
    per = min(sampai, util.hari_ini()) if mulai <= util.hari_ini() else sampai
    lr = reports.laba_rugi_bulan(conn, bulan)
    lalu = reports.laba_rugi_bulan(conn, util.geser_bulan(bulan, -1))
    akun = reports.saldo_akun(conn, per, hanya_aktif=True)
    stok = posisi_stok(conn, hanya_aktif=True)
    grafik, satuan = _grafik(conn, int(bulan[:4]), bulan)
    kosong = not stok and not conn.execute("SELECT 1 FROM transaksi_modal LIMIT 1").fetchone()
    return render_template(
        "dashboard.html",
        bulan=bulan,
        pilihan_bulan=util.daftar_bulan(),
        lr=lr,
        lalu=lalu,
        ubah_jual=reports.perubahan(lr["penjualan_bersih"], lalu["penjualan_bersih"]),
        ubah_laba=reports.perubahan(lr["laba_bersih"], lalu["laba_bersih"]),
        akun=akun,
        total_kas=sum(a["saldo"] for a in akun),
        per=per,
        persediaan=reports.nilai_persediaan(conn, per),
        jumlah_barang=len(stok),
        perlu_isi=[b for b in stok if b["status"] != "aman"][:6],
        jumlah_perlu_isi=sum(1 for b in stok if b["status"] != "aman"),
        grafik=grafik,
        satuan=satuan,
        terakhir=conn.execute(SQL_TERAKHIR).fetchall(),
        kosong=kosong,
        hutang=reports.ringkasan_hutang(reports.daftar_hutang(conn)),
    )
