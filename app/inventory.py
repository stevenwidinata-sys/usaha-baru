"""Perhitungan stok dan harga modal (HPP) rata-rata tertimbang.

Kartu stok (tabel mutasi_stok) tidak pernah diedit langsung. Setiap kali transaksi yang
menyentuh sebuah barang berubah, kartu stok barang itu dihitung ulang dari awal, sehingga
transaksi bertanggal mundur, edit, dan hapus tetap menghasilkan HPP yang benar.
"""
from .util import tanggal as fmt_tanggal

# Urutan dalam satu tanggal: stok awal dan pembelian dulu, lalu penjualan, opname terakhir.
PRIORITAS = {"stok_awal": 0, "pembelian": 1, "penjualan": 2, "opname": 3}


class StokTidakCukup(ValueError):
    def __init__(self, nama, tanggal, tersedia, diminta):
        self.nama, self.tanggal, self.tersedia, self.diminta = nama, tanggal, tersedia, diminta
        super().__init__(
            f"Stok {nama} tidak cukup pada {fmt_tanggal(tanggal)}: "
            f"tersedia {tersedia}, dibutuhkan {diminta}."
        )


def _kejadian(conn, barang_id):
    ev = []
    for r in conn.execute(
        "SELECT id, tanggal, jenis, qty, nilai_satuan, alasan FROM penyesuaian_stok WHERE barang_id = ?",
        (barang_id,),
    ):
        if r["jenis"] == "stok_awal":
            ket = "Stok awal"
        else:
            ket = "Stok opname" + (f" · {r['alasan']}" if r["alasan"] else "")
        ev.append({
            "tanggal": r["tanggal"], "sumber": r["jenis"], "ref_id": r["id"], "item_id": 0,
            "qty": r["qty"], "harga": r["nilai_satuan"] or 0, "ket": ket,
        })
    for r in conn.execute(
        "SELECT i.id AS item_id, p.id AS ref_id, p.tanggal, i.qty, i.harga_beli, p.no_faktur, p.pemasok "
        "FROM pembelian_item i JOIN pembelian p ON p.id = i.pembelian_id WHERE i.barang_id = ?",
        (barang_id,),
    ):
        ket = "Pembelian" + (f" {r['no_faktur']}" if r["no_faktur"] else "")
        if r["pemasok"]:
            ket += f" · {r['pemasok']}"
        ev.append({
            "tanggal": r["tanggal"], "sumber": "pembelian", "ref_id": r["ref_id"], "item_id": r["item_id"],
            "qty": r["qty"], "harga": r["harga_beli"], "ket": ket,
        })
    for r in conn.execute(
        "SELECT i.id AS item_id, p.id AS ref_id, p.tanggal, i.qty, p.no_nota "
        "FROM penjualan_item i JOIN penjualan p ON p.id = i.penjualan_id WHERE i.barang_id = ?",
        (barang_id,),
    ):
        ev.append({
            "tanggal": r["tanggal"], "sumber": "penjualan", "ref_id": r["ref_id"], "item_id": r["item_id"],
            "qty": -r["qty"], "harga": 0, "ket": f"Penjualan {r['no_nota']}",
        })
    ev.sort(key=lambda e: (e["tanggal"], PRIORITAS[e["sumber"]], e["ref_id"], e["item_id"]))
    return ev


def recalc_barang(conn, barang_id):
    """Hitung ulang kartu stok satu barang. Raise StokTidakCukup bila stok pernah minus."""
    row = conn.execute("SELECT nama FROM barang WHERE id = ?", (barang_id,)).fetchone()
    if row is None:
        return
    nama = row["nama"]
    conn.execute("DELETE FROM mutasi_stok WHERE barang_id = ?", (barang_id,))

    saldo, hpp = 0, 0.0
    for urut, e in enumerate(_kejadian(conn, barang_id), start=1):
        qty = e["qty"]
        if qty > 0:
            harga = hpp if e["sumber"] == "opname" else float(e["harga"])
            hpp = (saldo * hpp + qty * harga) / (saldo + qty)
            saldo += qty
            masuk, keluar = qty, 0
        else:
            keluar = -qty
            if keluar > saldo:
                raise StokTidakCukup(nama, e["tanggal"], saldo, keluar)
            harga = hpp
            saldo -= keluar
            masuk = 0
            if e["sumber"] == "penjualan":
                conn.execute("UPDATE penjualan_item SET hpp_satuan = ? WHERE id = ?", (hpp, e["item_id"]))
        conn.execute(
            "INSERT INTO mutasi_stok (barang_id, urut, tanggal, sumber, ref_id, keterangan, masuk, keluar, "
            "harga, nilai_mutasi, saldo_qty, hpp_rata, nilai_persediaan) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (barang_id, urut, e["tanggal"], e["sumber"], e["ref_id"], e["ket"], masuk, keluar,
             harga, abs(qty) * harga, saldo, hpp, saldo * hpp),
        )


def recalc_banyak(conn, barang_ids):
    for bid in sorted(set(barang_ids)):
        recalc_barang(conn, bid)


def stok_barang(conn, barang_id, per=None):
    """(saldo_qty, hpp_rata) sebuah barang, per tanggal tertentu atau terkini."""
    sql = "SELECT saldo_qty, hpp_rata FROM mutasi_stok WHERE barang_id = ?"
    args = [barang_id]
    if per:
        sql += " AND tanggal <= ?"
        args.append(per)
    row = conn.execute(sql + " ORDER BY urut DESC LIMIT 1", args).fetchone()
    return (row["saldo_qty"], row["hpp_rata"]) if row else (0, 0.0)


def posisi_stok(conn, per=None, hanya_aktif=False):
    """Daftar barang dengan stok, HPP rata-rata, nilai persediaan, dan status."""
    per = per or "9999-12-31"
    sql = (
        "SELECT b.*, COALESCE(m.saldo_qty, 0) AS stok, COALESCE(m.hpp_rata, 0) AS hpp, "
        "COALESCE(m.nilai_persediaan, 0) AS nilai FROM barang b "
        "LEFT JOIN mutasi_stok m ON m.id = (SELECT id FROM mutasi_stok WHERE barang_id = b.id "
        "AND tanggal <= ? ORDER BY urut DESC LIMIT 1)"
    )
    if hanya_aktif:
        sql += " WHERE b.aktif = 1"
    hasil = []
    for r in conn.execute(sql + " ORDER BY b.nama", (per,)):
        d = dict(r)
        if d["stok"] <= 0:
            d["status"] = "habis"
        elif d["stok"] < d["stok_minimum"]:
            d["status"] = "menipis"
        else:
            d["status"] = "aman"
        d["margin"] = (d["harga_jual"] - d["hpp"]) / d["harga_jual"] if d["harga_jual"] and d["hpp"] else None
        hasil.append(d)
    return hasil


def nilai_persediaan(conn, per=None):
    return sum(b["nilai"] for b in posisi_stok(conn, per))


def kartu_stok(conn, barang_id, mulai, sampai):
    """Saldo awal sebelum `mulai` dan daftar mutasi dalam periode."""
    awal_qty, awal_hpp = stok_barang(conn, barang_id, per=_sehari_sebelum(mulai))
    rows = conn.execute(
        "SELECT * FROM mutasi_stok WHERE barang_id = ? AND tanggal BETWEEN ? AND ? ORDER BY urut",
        (barang_id, mulai, sampai),
    ).fetchall()
    return {"saldo_awal": awal_qty, "hpp_awal": awal_hpp, "nilai_awal": awal_qty * awal_hpp, "mutasi": rows}


def _sehari_sebelum(iso):
    from datetime import date, timedelta

    return (date.fromisoformat(iso) - timedelta(days=1)).isoformat()
