"""Daftar blueprint halaman."""
from . import barang, kas, pembelian, penjualan, stok

BLUEPRINTS = [barang.bp, stok.bp, pembelian.bp, penjualan.bp, kas.bp]
