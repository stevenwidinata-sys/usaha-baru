# Menjalankan Usaha Baru secara online (PythonAnywhere)

Dengan panduan ini aplikasi berjalan di server PythonAnywhere, jadi bisa dibuka dari HP atau laptop mana saja
lewat `https://USERNAME.pythonanywhere.com`, **tanpa laptop menyala**.

Di semua langkah, ganti `USERNAME` dengan username akun PythonAnywhere kamu.

---

## 1. Daftar akun gratis

1. Buka <https://www.pythonanywhere.com> → **Pricing & signup** → **Create a Beginner account**.
2. Pilih **username** dengan cermat, karena username jadi alamat aplikasi: `USERNAME.pythonanywhere.com`.
3. Konfirmasi email.

## 2. Ambil kode dari GitHub

1. Di dashboard PythonAnywhere, buka menu **Consoles** → klik **Bash**.
2. Copy-paste perintah ini, lalu tekan Enter:

```bash
git clone https://github.com/stevenwidinata-sys/usaha-baru.git
cd usaha-baru
python3.13 -m venv ~/.venv-usaha
~/.venv-usaha/bin/pip install -r requirements.txt
mkdir -p data
```

> Kalau muncul `python3.13: command not found`, ulangi perintah ke-3 dan ke-4 dengan `python3.12`.
> Di langkah 3 nanti, pilih versi Python yang **sama**.

Tunggu sampai selesai. Kalau sudah kembali ke tanda `$`, tutup console.

## 3. Buat aplikasi web

1. Buka menu **Web** → **Add a new web app** → **Next**.
2. Pilih **Manual configuration**. Jangan pilih "Flask".
3. Pilih **Python 3.13**, atau versi yang dipakai di langkah 2 → **Next**.

Lalu di halaman **Web**, isi bagian-bagian ini:

| Bagian | Isi |
|---|---|
| **Virtualenv** | `/home/USERNAME/.venv-usaha` |
| **Static files**: URL | `/static/` |
| **Static files**: Directory | `/home/USERNAME/usaha-baru/app/static` |
| **Security → Force HTTPS** | **Enabled** |

## 4. Atur file WSGI dan password

1. Di halaman **Web**, bagian **Code**, klik link **WSGI configuration file**
   (namanya seperti `/var/www/USERNAME_pythonanywhere_com_wsgi.py`).
2. **Hapus semua isinya**, lalu ganti dengan:

```python
import os
import sys

os.environ["USAHA_PASSWORD"] = "GANTI-DENGAN-PASSWORD-KAMU"
os.environ["USAHA_HTTPS"] = "1"

sys.path.insert(0, "/home/USERNAME/usaha-baru")
from wsgi import application  # noqa
```

3. Ganti `USERNAME`, dan ganti `GANTI-DENGAN-PASSWORD-KAMU` dengan password untuk masuk ke aplikasi
   (minimal 8 karakter, jangan yang mudah ditebak). Klik **Save**.

> Password ini hanya dipakai kalau database belum punya password. Kalau nanti password diganti lewat menu
> **Pengaturan** di aplikasi, yang berlaku adalah password baru itu.

## 5. Pindahkan data dari laptop

Lewati langkah ini kalau mau mulai dengan data kosong.

1. Di laptop, **tutup** jendela hitam `jalankan.bat` supaya data tidak sedang dipakai.
2. Di PythonAnywhere, buka menu **Files** → masuk ke folder `usaha-baru` → `data`.
3. Klik **Upload a file** → pilih `C:\Project\Usaha_Baru\data\usaha.db`.

## 6. Nyalakan

1. Kembali ke menu **Web** → klik tombol hijau **Reload**.
2. Buka `https://USERNAME.pythonanywhere.com` → masuk dengan password dari langkah 4.

Kalau muncul halaman error, buka menu **Web** → **Log files** → **Error log**. Baris paling bawah biasanya
menjelaskan masalahnya.

## 7. Pasang di HP

- **Android (Chrome):** buka alamat aplikasi → menu **⋮** → **Instal aplikasi** atau **Tambahkan ke layar utama**.
- **iPhone (Safari):** buka alamat aplikasi → tombol **Bagikan** → **Tambah ke Layar Utama**.

Ikon "UB" akan muncul di layar utama. Aplikasinya terbuka layar penuh seperti aplikasi biasa.

---

## Hal penting setelah online

- **Pakai satu versi saja.** Setelah pindah ke online, jangan input data lagi di versi laptop. Kalau dua-duanya
  dipakai, datanya terpisah dan tidak bisa digabung.
- **Backup rutin**, misalnya seminggu sekali: menu **Pengaturan & backup** → **Unduh backup**. Bisa dari HP juga.
- **Akun gratis:** kalau di halaman **Web** ada tulisan bahwa situs akan dinonaktifkan pada tanggal tertentu,
  klik tombol perpanjangannya (misalnya *Run until 3 months from today*) sebelum tanggal itu.

## Memperbarui aplikasi

Kalau ada versi baru di GitHub, buka **Consoles → Bash** lalu jalankan:

```bash
cd ~/usaha-baru && git pull && ~/.venv-usaha/bin/pip install -r requirements.txt
```

Lalu **Web → Reload**. Data tidak ikut berubah.
