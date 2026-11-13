"""Daftar blueprint halaman."""
from . import barang, dashboard, hutang, kas, laporan, pembelian, pengaturan, penjualan, stok

BLUEPRINTS = [
    dashboard.bp,
    barang.bp,
    stok.bp,
    pembelian.bp,
    hutang.bp,
    penjualan.bp,
    kas.bp,
    laporan.bp,
    pengaturan.bp,
]
