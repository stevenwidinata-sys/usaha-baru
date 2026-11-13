"""Daftar blueprint halaman."""
from . import barang, pembelian, penjualan, stok

BLUEPRINTS = [barang.bp, stok.bp, pembelian.bp, penjualan.bp]
