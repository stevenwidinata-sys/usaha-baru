"""Daftar blueprint halaman."""
from . import barang, dashboard, hutang, kas, laporan, pembelian, pengaturan, penjualan, pwa, stok

BLUEPRINTS = [
    pwa.bp,
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
