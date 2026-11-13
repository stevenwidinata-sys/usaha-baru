"""Perhitungan laporan: laba rugi, arus kas, neraca, dan saldo akun."""
from datetime import date, timedelta

from . import util
from .db import KATEGORI_ADMIN
from .inventory import nilai_persediaan

AWAL = "0001-01-01"


def _satu(conn, sql, args):
    return conn.execute(sql, args).fetchone()[0] or 0


def laba_rugi(conn, mulai, sampai):
    args = (mulai, sampai)
    kotor = _satu(conn, "SELECT SUM(i.qty * i.harga_jual) FROM penjualan_item i "
                        "JOIN penjualan p ON p.id = i.penjualan_id WHERE p.tanggal BETWEEN ? AND ?", args)
    hpp = int(_satu(conn, "SELECT SUM(ROUND(i.qty * i.hpp_satuan)) FROM penjualan_item i "
                          "JOIN penjualan p ON p.id = i.penjualan_id WHERE p.tanggal BETWEEN ? AND ?", args))
    diskon = _satu(conn, "SELECT SUM(diskon) FROM penjualan WHERE tanggal BETWEEN ? AND ?", args)
    admin = _satu(conn, "SELECT SUM(biaya_admin) FROM penjualan WHERE tanggal BETWEEN ? AND ?", args)
    transaksi = _satu(conn, "SELECT COUNT(*) FROM penjualan WHERE tanggal BETWEEN ? AND ?", args)

    biaya = {
        r[0]: r[1]
        for r in conn.execute(
            "SELECT kategori, SUM(jumlah) FROM biaya WHERE tanggal BETWEEN ? AND ? GROUP BY kategori", args
        )
    }
    if admin:
        biaya[KATEGORI_ADMIN] = biaya.get(KATEGORI_ADMIN, 0) + admin
    total_biaya = sum(biaya.values())

    selisih = int(_satu(
        conn,
        "SELECT SUM(CASE WHEN masuk > 0 THEN nilai_mutasi ELSE -nilai_mutasi END) FROM mutasi_stok "
        "WHERE sumber = 'opname' AND tanggal BETWEEN ? AND ?",
        args,
    ))

    bersih = kotor - diskon
    laba_kotor = bersih - hpp
    laba_bersih = laba_kotor - total_biaya + selisih
    return {
        "mulai": mulai,
        "sampai": sampai,
        "transaksi": transaksi,
        "penjualan_kotor": kotor,
        "diskon": diskon,
        "penjualan_bersih": bersih,
        "hpp": hpp,
        "laba_kotor": laba_kotor,
        "biaya": sorted(biaya.items(), key=lambda kv: -kv[1]),
        "total_biaya": total_biaya,
        "selisih_stok": selisih,
        "laba_bersih": laba_bersih,
        "margin_kotor": laba_kotor / bersih if bersih else None,
        "margin_bersih": laba_bersih / bersih if bersih else None,
    }


def laba_rugi_bulan(conn, ym):
    return laba_rugi(conn, *util.periode_bulan(ym))


def laba_rugi_tahunan(conn, tahun):
    bulan = []
    for bl in range(1, 13):
        ym = f"{tahun:04d}-{bl:02d}"
        lr = laba_rugi_bulan(conn, ym)
        lr["ym"] = ym
        lr["nama"] = util.BULAN[bl - 1]
        bulan.append(lr)
    total = laba_rugi(conn, f"{tahun:04d}-01-01", f"{tahun:04d}-12-31")
    return {"tahun": tahun, "bulan": bulan, "total": total}


def saldo_akun(conn, per=None, hanya_aktif=False):
    per = per or "9999-12-31"
    rows = conn.execute(
        "SELECT a.*, COALESCE(SUM(v.jumlah), 0) AS saldo FROM akun a "
        "LEFT JOIN v_kas v ON v.akun_id = a.id AND v.tanggal <= ? GROUP BY a.id ORDER BY a.id",
        (per,),
    ).fetchall()
    return [dict(r) for r in rows if r["aktif"] or (not hanya_aktif and r["saldo"])]


def arus_kas(conn, mulai, sampai):
    saldo_awal = _satu(conn, "SELECT SUM(jumlah) FROM v_kas WHERE tanggal < ?", (mulai,))
    per_jenis = {
        r[0]: r[1]
        for r in conn.execute(
            "SELECT jenis, SUM(jumlah) FROM v_kas WHERE tanggal BETWEEN ? AND ? GROUP BY jenis", (mulai, sampai)
        )
    }
    per_metode = [
        (kode, label, per_jenis.get(f"penjualan_{kode}", 0)) for kode, label in util.METODE_BAYAR.items()
    ]
    masuk = [(f"Penjualan · {label.lower() if kode != 'qris' else label}", n) for kode, label, n in per_metode]
    masuk.append(("Setoran modal", per_jenis.get("setoran", 0)))
    keluar = [
        ("Pembelian barang", -per_jenis.get("pembelian", 0)),
        ("Biaya operasional", -(per_jenis.get("biaya", 0) + per_jenis.get("biaya_admin", 0))),
        ("Prive (ambil untuk pribadi)", -per_jenis.get("prive", 0)),
    ]
    total_masuk = sum(n for _, n in masuk)
    total_keluar = sum(n for _, n in keluar)
    total_penjualan = sum(n for _, _, n in per_metode)
    return {
        "mulai": mulai,
        "sampai": sampai,
        "saldo_awal": saldo_awal,
        "masuk": masuk,
        "keluar": keluar,
        "total_masuk": total_masuk,
        "total_keluar": total_keluar,
        "bersih": total_masuk - total_keluar,
        "saldo_akhir": saldo_awal + total_masuk - total_keluar,
        "per_akun": saldo_akun(conn, sampai),
        "per_metode": [
            {"kode": k, "label": lbl, "jumlah": n, "porsi": n / total_penjualan if total_penjualan else 0}
            for k, lbl, n in sorted(per_metode, key=lambda x: -x[2])
            if n
        ],
    }


def neraca(conn, per):
    akun = saldo_akun(conn, per)
    persediaan = nilai_persediaan(conn, per)
    total_kas = sum(a["saldo"] for a in akun)
    total_aset = total_kas + persediaan

    setoran = _satu(conn, "SELECT SUM(jumlah) FROM transaksi_modal WHERE jenis = 'setoran' AND tanggal <= ?", (per,))
    prive = _satu(conn, "SELECT SUM(jumlah) FROM transaksi_modal WHERE jenis = 'prive' AND tanggal <= ?", (per,))
    stok_awal = _satu(
        conn, "SELECT SUM(qty * nilai_satuan) FROM penyesuaian_stok WHERE jenis = 'stok_awal' AND tanggal <= ?",
        (per,),
    )
    awal_tahun = f"{per[:4]}-01-01"
    laba_berjalan = laba_rugi(conn, awal_tahun, per)["laba_bersih"]
    sebelum = (date.fromisoformat(awal_tahun) - timedelta(days=1)).isoformat()
    laba_lalu = laba_rugi(conn, AWAL, sebelum)["laba_bersih"]
    total_modal = setoran + stok_awal - prive + laba_lalu + laba_berjalan
    return {
        "per": per,
        "akun": akun,
        "persediaan": persediaan,
        "total_kas": total_kas,
        "total_aset": total_aset,
        "setoran": setoran,
        "stok_awal": stok_awal,
        "modal_disetor": setoran + stok_awal,
        "prive": prive,
        "laba_lalu": laba_lalu,
        "laba_berjalan": laba_berjalan,
        "total_modal": total_modal,
        "selisih": total_aset - total_modal,
        "seimbang": total_aset == total_modal,
    }


def perubahan(sekarang, sebelum):
    """Persentase perubahan, None bila tidak bisa dibandingkan."""
    if not sebelum:
        return None
    return (sekarang - sebelum) / abs(sebelum)
