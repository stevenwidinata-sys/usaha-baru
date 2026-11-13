-- Skema database Usaha Baru. Semua uang dalam rupiah (integer), kecuali harga modal rata-rata (REAL).

CREATE TABLE IF NOT EXISTS pengaturan (
    kunci TEXT PRIMARY KEY,
    nilai TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS akun (
    id INTEGER PRIMARY KEY,
    nama TEXT NOT NULL UNIQUE,
    jenis TEXT NOT NULL CHECK (jenis IN ('tunai', 'bank', 'ewallet')),
    aktif INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS kategori_biaya (
    id INTEGER PRIMARY KEY,
    nama TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS barang (
    id INTEGER PRIMARY KEY,
    kode TEXT NOT NULL UNIQUE,
    nama TEXT NOT NULL,
    satuan TEXT NOT NULL DEFAULT 'pcs',
    harga_jual INTEGER NOT NULL DEFAULT 0 CHECK (harga_jual >= 0),
    stok_minimum INTEGER NOT NULL DEFAULT 0 CHECK (stok_minimum >= 0),
    aktif INTEGER NOT NULL DEFAULT 1
);

-- cara_bayar 'lunas': total dibayar dari akun_id pada tanggal pembelian.
-- cara_bayar 'tempo': uang_muka (boleh 0) dibayar dari akun_id; sisanya jadi hutang sampai jatuh_tempo,
--                      dilunasi lewat pembayaran_hutang.
CREATE TABLE IF NOT EXISTS pembelian (
    id INTEGER PRIMARY KEY,
    tanggal TEXT NOT NULL,
    no_faktur TEXT,
    pemasok TEXT,
    akun_id INTEGER NOT NULL REFERENCES akun(id),
    catatan TEXT,
    cara_bayar TEXT NOT NULL DEFAULT 'lunas' CHECK (cara_bayar IN ('lunas', 'tempo')),
    jatuh_tempo TEXT,
    uang_muka INTEGER NOT NULL DEFAULT 0 CHECK (uang_muka >= 0)
);

CREATE TABLE IF NOT EXISTS pembayaran_hutang (
    id INTEGER PRIMARY KEY,
    pembelian_id INTEGER NOT NULL REFERENCES pembelian(id) ON DELETE CASCADE,
    tanggal TEXT NOT NULL,
    jumlah INTEGER NOT NULL CHECK (jumlah > 0),
    akun_id INTEGER NOT NULL REFERENCES akun(id),
    keterangan TEXT
);

CREATE TABLE IF NOT EXISTS pembelian_item (
    id INTEGER PRIMARY KEY,
    pembelian_id INTEGER NOT NULL REFERENCES pembelian(id) ON DELETE CASCADE,
    barang_id INTEGER NOT NULL REFERENCES barang(id),
    qty INTEGER NOT NULL CHECK (qty > 0),
    harga_beli INTEGER NOT NULL CHECK (harga_beli >= 0)
);

CREATE TABLE IF NOT EXISTS penjualan (
    id INTEGER PRIMARY KEY,
    tanggal TEXT NOT NULL,
    no_nota TEXT NOT NULL UNIQUE,
    pelanggan TEXT,
    diskon INTEGER NOT NULL DEFAULT 0 CHECK (diskon >= 0),
    metode_bayar TEXT NOT NULL CHECK (metode_bayar IN ('tunai', 'transfer', 'qris', 'debit')),
    akun_id INTEGER NOT NULL REFERENCES akun(id),
    no_referensi TEXT,
    biaya_admin INTEGER NOT NULL DEFAULT 0 CHECK (biaya_admin >= 0),
    catatan TEXT
);

CREATE TABLE IF NOT EXISTS penjualan_item (
    id INTEGER PRIMARY KEY,
    penjualan_id INTEGER NOT NULL REFERENCES penjualan(id) ON DELETE CASCADE,
    barang_id INTEGER NOT NULL REFERENCES barang(id),
    qty INTEGER NOT NULL CHECK (qty > 0),
    harga_jual INTEGER NOT NULL CHECK (harga_jual >= 0),
    hpp_satuan REAL NOT NULL DEFAULT 0
);

-- stok_awal: qty > 0 dengan nilai_satuan (harga modal awal), dihitung sebagai modal pemilik.
-- opname: qty = selisih stok fisik - stok sistem (boleh negatif), dinilai dengan harga modal rata-rata.
CREATE TABLE IF NOT EXISTS penyesuaian_stok (
    id INTEGER PRIMARY KEY,
    tanggal TEXT NOT NULL,
    barang_id INTEGER NOT NULL REFERENCES barang(id),
    jenis TEXT NOT NULL CHECK (jenis IN ('stok_awal', 'opname')),
    qty INTEGER NOT NULL CHECK (qty <> 0),
    nilai_satuan INTEGER,
    alasan TEXT
);

CREATE TABLE IF NOT EXISTS biaya (
    id INTEGER PRIMARY KEY,
    tanggal TEXT NOT NULL,
    kategori TEXT NOT NULL,
    keterangan TEXT,
    jumlah INTEGER NOT NULL CHECK (jumlah > 0),
    akun_id INTEGER NOT NULL REFERENCES akun(id)
);

CREATE TABLE IF NOT EXISTS transaksi_modal (
    id INTEGER PRIMARY KEY,
    tanggal TEXT NOT NULL,
    jenis TEXT NOT NULL CHECK (jenis IN ('setoran', 'prive')),
    jumlah INTEGER NOT NULL CHECK (jumlah > 0),
    akun_id INTEGER NOT NULL REFERENCES akun(id),
    keterangan TEXT
);

CREATE TABLE IF NOT EXISTS pindah_dana (
    id INTEGER PRIMARY KEY,
    tanggal TEXT NOT NULL,
    dari_akun_id INTEGER NOT NULL REFERENCES akun(id),
    ke_akun_id INTEGER NOT NULL REFERENCES akun(id),
    jumlah INTEGER NOT NULL CHECK (jumlah > 0),
    keterangan TEXT,
    CHECK (dari_akun_id <> ke_akun_id)
);

-- Kartu stok: hasil hitung ulang otomatis, jangan diisi manual.
CREATE TABLE IF NOT EXISTS mutasi_stok (
    id INTEGER PRIMARY KEY,
    barang_id INTEGER NOT NULL REFERENCES barang(id),
    urut INTEGER NOT NULL,
    tanggal TEXT NOT NULL,
    sumber TEXT NOT NULL,          -- stok_awal | pembelian | penjualan | opname
    ref_id INTEGER NOT NULL,       -- id transaksi induk (pembelian/penjualan/penyesuaian)
    keterangan TEXT,
    masuk INTEGER NOT NULL DEFAULT 0,
    keluar INTEGER NOT NULL DEFAULT 0,
    harga REAL NOT NULL,              -- harga per satuan mutasi ini
    nilai_mutasi INTEGER NOT NULL,    -- nilai rupiah mutasi (selalu positif)
    saldo_qty INTEGER NOT NULL,
    hpp_rata REAL NOT NULL,           -- nilai_persediaan / saldo_qty
    nilai_persediaan INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_mutasi_barang ON mutasi_stok (barang_id, urut);
CREATE INDEX IF NOT EXISTS ix_mutasi_tanggal ON mutasi_stok (tanggal);
CREATE INDEX IF NOT EXISTS ix_penjualan_tanggal ON penjualan (tanggal);
CREATE INDEX IF NOT EXISTS ix_pembelian_tanggal ON pembelian (tanggal);
CREATE INDEX IF NOT EXISTS ix_penjualan_item_barang ON penjualan_item (barang_id);
CREATE INDEX IF NOT EXISTS ix_pembelian_item_barang ON pembelian_item (barang_id);
CREATE INDEX IF NOT EXISTS ix_biaya_tanggal ON biaya (tanggal);
CREATE INDEX IF NOT EXISTS ix_bayar_hutang_pembelian ON pembayaran_hutang (pembelian_id);

-- Semua uang masuk (+) dan keluar (-) per akun.
DROP VIEW IF EXISTS v_kas;
CREATE VIEW v_kas AS
    SELECT tanggal, akun_id, 'setoran' AS jenis, jumlah FROM transaksi_modal WHERE jenis = 'setoran'
    UNION ALL
    SELECT tanggal, akun_id, 'prive', -jumlah FROM transaksi_modal WHERE jenis = 'prive'
    UNION ALL
    SELECT p.tanggal, p.akun_id, 'penjualan_' || p.metode_bayar,
           (SELECT COALESCE(SUM(i.qty * i.harga_jual), 0) FROM penjualan_item i WHERE i.penjualan_id = p.id) - p.diskon
    FROM penjualan p
    UNION ALL
    SELECT tanggal, akun_id, 'biaya_admin', -biaya_admin FROM penjualan WHERE biaya_admin > 0
    UNION ALL
    SELECT b.tanggal, b.akun_id, 'pembelian',
           -(SELECT COALESCE(SUM(i.qty * i.harga_beli), 0) FROM pembelian_item i WHERE i.pembelian_id = b.id)
    FROM pembelian b WHERE b.cara_bayar = 'lunas'
    UNION ALL
    SELECT tanggal, akun_id, 'pembelian', -uang_muka FROM pembelian WHERE cara_bayar = 'tempo' AND uang_muka > 0
    UNION ALL
    SELECT tanggal, akun_id, 'bayar_hutang', -jumlah FROM pembayaran_hutang
    UNION ALL
    SELECT tanggal, akun_id, 'biaya', -jumlah FROM biaya
    UNION ALL
    SELECT tanggal, dari_akun_id, 'pindah_keluar', -jumlah FROM pindah_dana
    UNION ALL
    SELECT tanggal, ke_akun_id, 'pindah_masuk', jumlah FROM pindah_dana;
