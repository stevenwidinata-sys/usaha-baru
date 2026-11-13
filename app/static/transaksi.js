// Form transaksi multi-barang (penjualan & pembelian): tambah/hapus baris, hitung total, metode bayar.
(function () {
  var form = document.getElementById('form-transaksi');
  if (!form) return;
  var mode = form.dataset.mode; // 'jual' | 'beli'
  var tbody = document.getElementById('baris-item');
  var tpl = document.getElementById('tpl-baris');

  function num(s) { return parseInt(String(s || '').replace(/[^\d]/g, ''), 10) || 0; }
  function rp(n) { return 'Rp ' + Math.round(n).toLocaleString('id-ID'); }
  function el(id) { return document.getElementById(id); }
  function setTeks(id, teks) { var e = el(id); if (e) e.textContent = teks; }
  function opsi(row) { var s = row.querySelector('.sel-barang'); return s && s.value ? s.selectedOptions[0] : null; }
  function baris() { return Array.prototype.slice.call(tbody.querySelectorAll('.baris-item')); }

  function pilihBarang(row, isiHarga) {
    var o = opsi(row);
    var info = row.querySelector('.info-stok');
    if (!o) { info.textContent = ''; return; }
    if (isiHarga) row.querySelector('.harga').value = o.dataset.harga || '';
    info.textContent = 'Stok ' + o.dataset.stok + ' ' + o.dataset.satuan;
  }

  function hitung() {
    var sub = 0, hpp = 0, item = 0;
    baris().forEach(function (row) {
      var q = num(row.querySelector('.qty').value);
      var h = num(row.querySelector('.harga').value);
      row.querySelector('.subtotal').textContent = rp(q * h);
      sub += q * h;
      var o = opsi(row);
      var info = row.querySelector('.info-stok');
      if (!o) return;
      item += q;
      hpp += q * parseFloat(o.dataset.hpp || '0');
      if (mode === 'jual') {
        var stok = parseInt(o.dataset.stok, 10) || 0;
        var lebih = q > stok;
        info.classList.toggle('oranye', lebih);
        info.classList.toggle('tebal', lebih);
        info.textContent = lebih ? 'Melebihi stok (sisa ' + stok + ' ' + o.dataset.satuan + ')'
                                 : 'Stok ' + stok + ' ' + o.dataset.satuan;
      }
    });
    var diskon = num(el('diskon') && el('diskon').value);
    var total = sub - diskon;
    setTeks('subtotal', rp(sub));
    setTeks('jumlah-item', item);
    setTeks('total', rp(total));
    if (mode === 'jual') {
      setTeks('hpp', rp(hpp));
      setTeks('laba', rp(total - hpp));
      var diterima = num(el('diterima') && el('diterima').value);
      setTeks('kembalian', !diterima ? '–' : diterima >= total ? rp(diterima - total) : 'Kurang ' + rp(total - diterima));
    }
    return total;
  }

  function tambahBaris() {
    var row = tpl.content.firstElementChild.cloneNode(true);
    tbody.appendChild(row);
    row.querySelector('.sel-barang').focus();
    hitung();
  }

  tbody.addEventListener('input', hitung);
  tbody.addEventListener('change', function (e) {
    if (e.target.classList.contains('sel-barang')) pilihBarang(e.target.closest('tr'), true);
    hitung();
  });
  tbody.addEventListener('click', function (e) {
    var step = e.target.closest('[data-step]');
    var hapus = e.target.closest('.hapus-baris');
    if (step) {
      var input = step.closest('tr').querySelector('.qty');
      input.value = Math.max(1, num(input.value) + parseInt(step.dataset.step, 10));
      hitung();
    } else if (hapus) {
      if (baris().length > 1) hapus.closest('tr').remove();
      else {
        var row = hapus.closest('tr');
        row.querySelector('.sel-barang').value = '';
        row.querySelector('.qty').value = 1;
        row.querySelector('.harga').value = '';
        pilihBarang(row, false);
      }
      hitung();
    }
  });
  var tombolTambah = el('tambah-baris');
  if (tombolTambah) tombolTambah.addEventListener('click', tambahBaris);
  ['diskon', 'diterima'].forEach(function (id) { if (el(id)) el(id).addEventListener('input', hitung); });

  // Metode bayar (penjualan)
  function aturMetode() {
    var dipilih = form.querySelector('input[name="metode_bayar"]:checked');
    if (!dipilih) return;
    var tunai = dipilih.value === 'tunai';
    el('bagian-tunai').classList.toggle('tersembunyi', !tunai);
    el('bagian-nontunai').classList.toggle('tersembunyi', tunai);
    var sel = el('akun_nontunai');
    if (!tunai && sel && !sel.dataset.diubah) {
      var mau = dipilih.value === 'qris' ? 'ewallet' : 'bank';
      for (var i = 0; i < sel.options.length; i++) {
        if (sel.options[i].dataset.jenis === mau) { sel.selectedIndex = i; break; }
      }
    }
    var ref = el('no_referensi');
    if (ref) ref.placeholder = { qris: 'ID transaksi QRIS', debit: 'No. approval / 4 digit akhir kartu', transfer: 'No. referensi transfer' }[dipilih.value] || '';
  }
  form.querySelectorAll('input[name="metode_bayar"]').forEach(function (r) { r.addEventListener('change', aturMetode); });
  if (el('akun_nontunai')) el('akun_nontunai').addEventListener('change', function () { this.dataset.diubah = '1'; });
  form.querySelectorAll('[data-bayar]').forEach(function (b) {
    b.addEventListener('click', function () {
      el('diterima').value = b.dataset.bayar === 'pas' ? hitung() : b.dataset.bayar;
      hitung();
    });
  });

  baris().forEach(function (row) { pilihBarang(row, false); });
  aturMetode();
  hitung();
})();
