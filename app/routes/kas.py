"""Biaya operasional, modal & prive, dan pindah dana antar akun."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import util
from ..db import get_db
from ._bantu import akun_valid, bulan_dari_request, daftar_akun, tanggal_dari_form

bp = Blueprint("kas", __name__)


def _gagal(pesan, tujuan):
    flash(pesan, "galat")
    return redirect(tujuan)


# ---------- Biaya operasional ----------

def _kategori(conn):
    return [r["nama"] for r in conn.execute("SELECT nama FROM kategori_biaya ORDER BY id")]


def _form_biaya(conn):
    f = request.form
    data = {
        "tanggal": tanggal_dari_form(),
        "kategori": f.get("kategori", "").strip(),
        "keterangan": f.get("keterangan", "").strip() or None,
        "jumlah": util.parse_int(f.get("jumlah")),
        "akun_id": util.parse_int(f.get("akun_id")),
    }
    if not data["tanggal"] or not data["kategori"]:
        return data, "Isi tanggal dan kategori biaya."
    if not data["jumlah"] or data["jumlah"] <= 0:
        return data, "Jumlah biaya harus lebih dari 0."
    if not akun_valid(conn, data["akun_id"]):
        return data, "Pilih akun yang dipakai membayar."
    return data, None


@bp.route("/biaya", methods=["GET", "POST"])
def biaya():
    conn = get_db()
    if request.method == "POST":
        data, galat = _form_biaya(conn)
        if galat:
            return _gagal(galat, url_for("kas.biaya"))
        conn.execute(
            "INSERT INTO biaya (tanggal, kategori, keterangan, jumlah, akun_id) VALUES (?, ?, ?, ?, ?)",
            (data["tanggal"], data["kategori"], data["keterangan"], data["jumlah"], data["akun_id"]),
        )
        conn.commit()
        flash(f"Biaya {data['kategori']} {util.rupiah(data['jumlah'])} dicatat.", "sukses")
        return redirect(url_for("kas.biaya", bulan=data["tanggal"][:7]))

    bulan = bulan_dari_request()
    mulai, sampai = util.periode_bulan(bulan)
    rows = conn.execute(
        "SELECT b.*, a.nama AS akun FROM biaya b JOIN akun a ON a.id = b.akun_id "
        "WHERE b.tanggal BETWEEN ? AND ? ORDER BY b.tanggal DESC, b.id DESC",
        (mulai, sampai),
    ).fetchall()
    admin = conn.execute(
        "SELECT COALESCE(SUM(biaya_admin), 0) FROM penjualan WHERE tanggal BETWEEN ? AND ?", (mulai, sampai)
    ).fetchone()[0]
    per_kategori = {}
    for r in rows:
        per_kategori[r["kategori"]] = per_kategori.get(r["kategori"], 0) + r["jumlah"]
    return render_template(
        "kas/biaya.html",
        rows=rows,
        bulan=bulan,
        pilihan_bulan=util.daftar_bulan(),
        kategori=_kategori(conn),
        akun=daftar_akun(conn),
        per_kategori=sorted(per_kategori.items(), key=lambda kv: -kv[1]),
        admin=admin,
        total=sum(r["jumlah"] for r in rows),
        hari_ini=util.hari_ini(),
        edit=None,
    )


@bp.route("/biaya/<int:biaya_id>/edit", methods=["GET", "POST"])
def edit_biaya(biaya_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM biaya WHERE id = ?", (biaya_id,)).fetchone() or abort(404)
    if request.method == "POST":
        data, galat = _form_biaya(conn)
        if galat:
            return _gagal(galat, url_for("kas.edit_biaya", biaya_id=biaya_id))
        conn.execute(
            "UPDATE biaya SET tanggal = ?, kategori = ?, keterangan = ?, jumlah = ?, akun_id = ? WHERE id = ?",
            (data["tanggal"], data["kategori"], data["keterangan"], data["jumlah"], data["akun_id"], biaya_id),
        )
        conn.commit()
        flash("Biaya diperbarui.", "sukses")
        return redirect(url_for("kas.biaya", bulan=data["tanggal"][:7]))
    return render_template(
        "kas/biaya_edit.html", edit=row, kategori=_kategori(conn), akun=daftar_akun(conn, hanya_aktif=False)
    )


@bp.post("/biaya/<int:biaya_id>/hapus")
def hapus_biaya(biaya_id):
    conn = get_db()
    row = conn.execute("SELECT tanggal FROM biaya WHERE id = ?", (biaya_id,)).fetchone() or abort(404)
    conn.execute("DELETE FROM biaya WHERE id = ?", (biaya_id,))
    conn.commit()
    flash("Biaya dihapus.", "sukses")
    return redirect(url_for("kas.biaya", bulan=row["tanggal"][:7]))


# ---------- Modal & prive ----------

@bp.route("/modal", methods=["GET", "POST"])
def modal():
    conn = get_db()
    if request.method == "POST":
        f = request.form
        jenis = f.get("jenis")
        tanggal = tanggal_dari_form()
        jumlah = util.parse_int(f.get("jumlah"))
        akun_id = util.parse_int(f.get("akun_id"))
        if jenis not in ("setoran", "prive") or not tanggal or not jumlah or jumlah <= 0:
            return _gagal("Isi jenis, tanggal, dan jumlah dengan benar.", url_for("kas.modal"))
        if not akun_valid(conn, akun_id):
            return _gagal("Pilih akun.", url_for("kas.modal"))
        conn.execute(
            "INSERT INTO transaksi_modal (tanggal, jenis, jumlah, akun_id, keterangan) VALUES (?, ?, ?, ?, ?)",
            (tanggal, jenis, jumlah, akun_id, f.get("keterangan", "").strip() or None),
        )
        conn.commit()
        flash(f"{'Setoran modal' if jenis == 'setoran' else 'Prive'} {util.rupiah(jumlah)} dicatat.", "sukses")
        return redirect(url_for("kas.modal"))

    rows = conn.execute(
        "SELECT m.*, a.nama AS akun FROM transaksi_modal m JOIN akun a ON a.id = m.akun_id "
        "ORDER BY m.tanggal DESC, m.id DESC"
    ).fetchall()
    stok_awal = conn.execute(
        "SELECT COALESCE(SUM(qty * nilai_satuan), 0) FROM penyesuaian_stok WHERE jenis = 'stok_awal'"
    ).fetchone()[0]
    return render_template(
        "kas/modal.html",
        rows=rows,
        akun=daftar_akun(conn),
        setoran=sum(r["jumlah"] for r in rows if r["jenis"] == "setoran"),
        prive=sum(r["jumlah"] for r in rows if r["jenis"] == "prive"),
        stok_awal=stok_awal,
        hari_ini=util.hari_ini(),
    )


@bp.post("/modal/<int:modal_id>/hapus")
def hapus_modal(modal_id):
    conn = get_db()
    conn.execute("DELETE FROM transaksi_modal WHERE id = ?", (modal_id,))
    conn.commit()
    flash("Transaksi modal dihapus.", "sukses")
    return redirect(url_for("kas.modal"))


# ---------- Pindah dana ----------

@bp.route("/pindah-dana", methods=["GET", "POST"])
def pindah_dana():
    conn = get_db()
    if request.method == "POST":
        f = request.form
        tanggal = tanggal_dari_form()
        dari, ke = util.parse_int(f.get("dari_akun_id")), util.parse_int(f.get("ke_akun_id"))
        jumlah = util.parse_int(f.get("jumlah"))
        if not tanggal or not jumlah or jumlah <= 0:
            return _gagal("Isi tanggal dan jumlah dengan benar.", url_for("kas.pindah_dana"))
        if not akun_valid(conn, dari) or not akun_valid(conn, ke) or dari == ke:
            return _gagal("Pilih dua akun yang berbeda.", url_for("kas.pindah_dana"))
        conn.execute(
            "INSERT INTO pindah_dana (tanggal, dari_akun_id, ke_akun_id, jumlah, keterangan) VALUES (?, ?, ?, ?, ?)",
            (tanggal, dari, ke, jumlah, f.get("keterangan", "").strip() or None),
        )
        conn.commit()
        flash(f"Pindah dana {util.rupiah(jumlah)} dicatat.", "sukses")
        return redirect(url_for("kas.pindah_dana"))

    rows = conn.execute(
        "SELECT p.*, d.nama AS dari, k.nama AS ke FROM pindah_dana p "
        "JOIN akun d ON d.id = p.dari_akun_id JOIN akun k ON k.id = p.ke_akun_id "
        "ORDER BY p.tanggal DESC, p.id DESC LIMIT 200"
    ).fetchall()
    saldo = {r[0]: r[1] for r in conn.execute("SELECT akun_id, SUM(jumlah) FROM v_kas GROUP BY akun_id")}
    akun = daftar_akun(conn)
    return render_template(
        "kas/pindah_dana.html",
        rows=rows,
        akun=akun,
        saldo=[(a, saldo.get(a["id"], 0)) for a in akun],
        hari_ini=util.hari_ini(),
    )


@bp.post("/pindah-dana/<int:pindah_id>/hapus")
def hapus_pindah(pindah_id):
    conn = get_db()
    conn.execute("DELETE FROM pindah_dana WHERE id = ?", (pindah_id,))
    conn.commit()
    flash("Pindah dana dihapus.", "sukses")
    return redirect(url_for("kas.pindah_dana"))
