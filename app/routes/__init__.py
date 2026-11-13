"""Daftar blueprint halaman."""
from . import barang, kas, laporan, pembelian, penjualan, stok

BLUEPRINTS = [barang.bp, stok.bp, pembelian.bp, penjualan.bp, kas.bp, laporan.bp]
