"""Fungsi bantu: format rupiah, tanggal Indonesia, periode bulan, parsing angka."""
from datetime import date, timedelta

BULAN = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]
BULAN_PENDEK = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]

METODE_BAYAR = {
    "tunai": "Tunai",
    "transfer": "Transfer bank",
    "qris": "QRIS / e-wallet",
    "debit": "Kartu debit",
}
JENIS_AKUN = {"tunai": "Kas tunai", "bank": "Bank", "ewallet": "E-wallet"}


def angka(n):
    """1250000 -> '1.250.000'"""
    n = round(n or 0)
    s = f"{abs(n):,}".replace(",", ".")
    return f"-{s}" if n < 0 else s


def rupiah(n):
    """1250000 -> 'Rp 1.250.000', -5000 -> '−Rp 5.000'"""
    n = round(n or 0)
    s = "Rp " + f"{abs(n):,}".replace(",", ".")
    return f"−{s}" if n < 0 else s


def rupiah_kurung(n):
    """Untuk laporan: angka pengurang ditulis dalam kurung."""
    return f"({rupiah(abs(n))})" if round(n or 0) else rupiah(0)


def persen(nilai, dari, desimal=1):
    if not dari:
        return "–"
    return f"{nilai / dari * 100:.{desimal}f}%".replace(".", ",")


def ke_date(iso):
    if isinstance(iso, date):
        return iso
    return date.fromisoformat(str(iso)[:10])


def tanggal(iso):
    """'2026-10-28' -> '28 Okt 2026'"""
    if not iso:
        return ""
    d = ke_date(iso)
    return f"{d.day:02d} {BULAN_PENDEK[d.month - 1]} {d.year}"


def tanggal_panjang(iso):
    d = ke_date(iso)
    return f"{d.day} {BULAN[d.month - 1]} {d.year}"


def hari_ini():
    return date.today().isoformat()


def bulan_ini():
    return date.today().strftime("%Y-%m")


def valid_bulan(ym):
    try:
        th, bl = str(ym).split("-")
        th, bl = int(th), int(bl)
        return 1900 <= th <= 9999 and 1 <= bl <= 12
    except (ValueError, AttributeError):
        return False


def periode_bulan(ym):
    """'2026-10' -> ('2026-10-01', '2026-10-31')"""
    th, bl = (int(x) for x in ym.split("-"))
    mulai = date(th, bl, 1)
    berikut = date(th + (bl == 12), bl % 12 + 1, 1)
    return mulai.isoformat(), (berikut - timedelta(days=1)).isoformat()


def label_bulan(ym):
    th, bl = (int(x) for x in ym.split("-"))
    return f"{BULAN[bl - 1]} {th}"


def geser_bulan(ym, delta):
    th, bl = (int(x) for x in ym.split("-"))
    idx = th * 12 + (bl - 1) + delta
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def daftar_bulan(jumlah=24, akhir=None):
    """Pilihan bulan untuk dropdown, terbaru dulu."""
    akhir = akhir or bulan_ini()
    return [(geser_bulan(akhir, -i), label_bulan(geser_bulan(akhir, -i))) for i in range(jumlah)]


def parse_int(teks, default=None):
    """Terima '1.250.000', 'Rp 1.250.000', '1250000' -> 1250000."""
    if teks is None:
        return default
    s = str(teks).strip().replace("Rp", "").replace(" ", "").replace(".", "").replace(",", "")
    neg = s.startswith("-") or s.startswith("−")
    s = s.lstrip("-−")
    if not s.isdigit():
        return default
    return -int(s) if neg else int(s)


def parse_tanggal(teks):
    try:
        return date.fromisoformat(str(teks).strip()).isoformat()
    except ValueError:
        return None
