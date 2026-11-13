"""Operasi tulis transaksi yang memengaruhi stok. Tidak melakukan commit; pemanggil yang commit/rollback."""
from .inventory import recalc_banyak, stok_barang


class InputTidakValid(ValueError):
    pass


def _cek_items(items):
    if not items:
        raise InputTidakValid("Tambahkan minimal satu barang.")
    for it in items:
        if it["qty"] <= 0:
            raise InputTidakValid("Jumlah barang harus lebih dari 0.")
        if it["harga"] < 0:
            raise InputTidakValid("Harga tidak boleh negatif.")


def _barang_ids(conn, tabel, kolom, induk_id):
    return {r[0] for r in conn.execute(f"SELECT barang_id FROM {tabel} WHERE {kolom} = ?", (induk_id,))}


# ---------- Pembelian ----------

def simpan_pembelian(conn, data, items, pembelian_id=None):
    _cek_items(items)
    lama = set()
    if pembelian_id:
        lama = _barang_ids(conn, "pembelian_item", "pembelian_id", pembelian_id)
        conn.execute(
            "UPDATE pembelian SET tanggal = ?, no_faktur = ?, pemasok = ?, akun_id = ?, catatan = ? WHERE id = ?",
            (data["tanggal"], data.get("no_faktur"), data.get("pemasok"), data["akun_id"], data.get("catatan"),
             pembelian_id),
        )
        conn.execute("DELETE FROM pembelian_item WHERE pembelian_id = ?", (pembelian_id,))
    else:
        pembelian_id = conn.execute(
            "INSERT INTO pembelian (tanggal, no_faktur, pemasok, akun_id, catatan) VALUES (?, ?, ?, ?, ?)",
            (data["tanggal"], data.get("no_faktur"), data.get("pemasok"), data["akun_id"], data.get("catatan")),
        ).lastrowid
    conn.executemany(
        "INSERT INTO pembelian_item (pembelian_id, barang_id, qty, harga_beli) VALUES (?, ?, ?, ?)",
        [(pembelian_id, it["barang_id"], it["qty"], it["harga"]) for it in items],
    )
    recalc_banyak(conn, lama | {it["barang_id"] for it in items})
    return pembelian_id


def hapus_pembelian(conn, pembelian_id):
    ids = _barang_ids(conn, "pembelian_item", "pembelian_id", pembelian_id)
    conn.execute("DELETE FROM pembelian WHERE id = ?", (pembelian_id,))
    recalc_banyak(conn, ids)


# ---------- Penjualan ----------

def nomor_nota_berikut(conn):
    n = conn.execute(
        "SELECT MAX(CAST(SUBSTR(no_nota, 4) AS INTEGER)) FROM penjualan WHERE no_nota LIKE 'PJ-%'"
    ).fetchone()[0]
    return f"PJ-{(n or 0) + 1:04d}"


def simpan_penjualan(conn, data, items, penjualan_id=None):
    _cek_items(items)
    subtotal = sum(it["qty"] * it["harga"] for it in items)
    diskon = data.get("diskon") or 0
    if diskon < 0 or diskon > subtotal:
        raise InputTidakValid("Diskon tidak boleh melebihi subtotal.")
    metode = data["metode_bayar"]
    biaya_admin = 0 if metode == "tunai" else (data.get("biaya_admin") or 0)
    if biaya_admin < 0 or biaya_admin > subtotal - diskon:
        raise InputTidakValid("Potongan biaya admin tidak valid.")
    no_ref = None if metode == "tunai" else (data.get("no_referensi") or None)
    nilai = (data["tanggal"], data.get("pelanggan"), diskon, metode, data["akun_id"], no_ref, biaya_admin,
             data.get("catatan"))

    lama = set()
    if penjualan_id:
        lama = _barang_ids(conn, "penjualan_item", "penjualan_id", penjualan_id)
        conn.execute(
            "UPDATE penjualan SET tanggal = ?, pelanggan = ?, diskon = ?, metode_bayar = ?, akun_id = ?, "
            "no_referensi = ?, biaya_admin = ?, catatan = ? WHERE id = ?",
            (*nilai, penjualan_id),
        )
        conn.execute("DELETE FROM penjualan_item WHERE penjualan_id = ?", (penjualan_id,))
    else:
        penjualan_id = conn.execute(
            "INSERT INTO penjualan (tanggal, pelanggan, diskon, metode_bayar, akun_id, no_referensi, biaya_admin, "
            "catatan, no_nota) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (*nilai, nomor_nota_berikut(conn)),
        ).lastrowid
    conn.executemany(
        "INSERT INTO penjualan_item (penjualan_id, barang_id, qty, harga_jual) VALUES (?, ?, ?, ?)",
        [(penjualan_id, it["barang_id"], it["qty"], it["harga"]) for it in items],
    )
    recalc_banyak(conn, lama | {it["barang_id"] for it in items})
    return penjualan_id


def hapus_penjualan(conn, penjualan_id):
    ids = _barang_ids(conn, "penjualan_item", "penjualan_id", penjualan_id)
    conn.execute("DELETE FROM penjualan WHERE id = ?", (penjualan_id,))
    recalc_banyak(conn, ids)


# ---------- Penyesuaian stok ----------

def simpan_stok_awal(conn, tanggal, barang_id, qty, nilai_satuan, alasan=None):
    if qty <= 0:
        raise InputTidakValid("Jumlah stok awal harus lebih dari 0.")
    if nilai_satuan is None or nilai_satuan < 0:
        raise InputTidakValid("Isi harga modal per satuan untuk stok awal.")
    pid = conn.execute(
        "INSERT INTO penyesuaian_stok (tanggal, barang_id, jenis, qty, nilai_satuan, alasan) "
        "VALUES (?, ?, 'stok_awal', ?, ?, ?)",
        (tanggal, barang_id, qty, nilai_satuan, alasan),
    ).lastrowid
    recalc_banyak(conn, [barang_id])
    return pid


def simpan_opname(conn, tanggal, barang_id, stok_fisik, alasan=None):
    if stok_fisik is None or stok_fisik < 0:
        raise InputTidakValid("Stok fisik tidak boleh negatif.")
    sistem, _ = stok_barang(conn, barang_id, per=tanggal)
    selisih = stok_fisik - sistem
    if selisih == 0:
        raise InputTidakValid("Stok fisik sama dengan stok di sistem, tidak ada selisih.")
    pid = conn.execute(
        "INSERT INTO penyesuaian_stok (tanggal, barang_id, jenis, qty, alasan) VALUES (?, ?, 'opname', ?, ?)",
        (tanggal, barang_id, selisih, alasan),
    ).lastrowid
    recalc_banyak(conn, [barang_id])
    return pid


def hapus_penyesuaian(conn, penyesuaian_id):
    row = conn.execute("SELECT barang_id FROM penyesuaian_stok WHERE id = ?", (penyesuaian_id,)).fetchone()
    if row:
        conn.execute("DELETE FROM penyesuaian_stok WHERE id = ?", (penyesuaian_id,))
        recalc_banyak(conn, [row["barang_id"]])
