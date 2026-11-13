"""Daftar blueprint halaman."""
from . import barang, dashboard, kas, laporan, pembelian, penjualan, stok

BLUEPRINTS = [dashboard.bp, barang.bp, stok.bp, pembelian.bp, penjualan.bp, kas.bp, laporan.bp]
