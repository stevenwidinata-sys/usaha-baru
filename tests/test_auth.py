import pytest

from app import create_app


@pytest.fixture
def app_login(tmp_path, monkeypatch):
    monkeypatch.delenv("USAHA_PASSWORD", raising=False)
    return create_app({"DATABASE": str(tmp_path / "a.db"), "TESTING": True})


def buat_password(client, pw="rahasia123"):
    return client.post("/buat-password", data={"password": pw, "konfirmasi": pw}, follow_redirects=True)


def test_pertama_kali_diarahkan_buat_password(app_login):
    c = app_login.test_client()
    r = c.get("/")
    assert r.status_code == 302 and "/buat-password" in r.headers["Location"]
    assert "Dashboard" in buat_password(c).get_data(as_text=True)


def test_password_terlalu_pendek_atau_beda(app_login):
    c = app_login.test_client()
    r = c.post("/buat-password", data={"password": "123", "konfirmasi": "123"})
    assert "Password minimal 8 karakter" in r.get_data(as_text=True)
    r = c.post("/buat-password", data={"password": "rahasia123", "konfirmasi": "rahasia124"}, follow_redirects=True)
    assert "tidak sama" in r.get_data(as_text=True)


def test_halaman_terkunci_tanpa_login(app_login):
    buat_password(app_login.test_client())
    c = app_login.test_client()  # perangkat lain, belum masuk
    for url in ["/", "/penjualan", "/laporan/neraca", "/pengaturan/backup"]:
        r = c.get(url)
        assert r.status_code == 302 and "/masuk" in r.headers["Location"], url
    assert c.post("/biaya", data={}).status_code == 302
    assert c.get("/buat-password").status_code == 302  # tidak bisa membuat password baru lagi


def test_masuk_dan_keluar(app_login):
    buat_password(app_login.test_client())
    c = app_login.test_client()
    r = c.post("/masuk?next=/penjualan", data={"password": "salah-salah"}, follow_redirects=True)
    assert "Password salah" in r.get_data(as_text=True)
    r = c.post("/masuk?next=/penjualan", data={"password": "rahasia123"})
    assert r.headers["Location"].endswith("/penjualan")
    assert c.get("/").status_code == 200
    c.post("/keluar")
    assert c.get("/").status_code == 302


def test_next_ke_situs_lain_diabaikan(app_login):
    buat_password(app_login.test_client())
    c = app_login.test_client()
    r = c.post("/masuk?next=//situs-jahat.com", data={"password": "rahasia123"})
    assert r.headers["Location"] == "/"


def test_ganti_password(app_login):
    c = app_login.test_client()
    buat_password(c)
    r = c.post("/pengaturan/password", data={"lama": "salah", "password": "baru12345", "konfirmasi": "baru12345"},
               follow_redirects=True)
    assert "Password lama salah" in r.get_data(as_text=True)
    c.post("/pengaturan/password", data={"lama": "rahasia123", "password": "baru12345", "konfirmasi": "baru12345"})
    c2 = app_login.test_client()
    assert c2.post("/masuk", data={"password": "baru12345"}).status_code == 302


def test_password_awal_dari_variabel_lingkungan(tmp_path, monkeypatch):
    monkeypatch.setenv("USAHA_PASSWORD", "dari-env-123")
    app = create_app({"DATABASE": str(tmp_path / "env.db"), "TESTING": True})
    c = app.test_client()
    assert "/masuk" in c.get("/").headers["Location"]
    assert c.post("/masuk", data={"password": "dari-env-123"}).status_code == 302
    assert c.get("/").status_code == 200


def test_database_diganti_tanpa_password_tetap_terkunci(tmp_path, monkeypatch):
    monkeypatch.setenv("USAHA_PASSWORD", "dari-env-123")
    app = create_app({"DATABASE": str(tmp_path / "g.db"), "TESTING": True})
    from app.db import connect
    conn = connect(app.config["DATABASE"])
    conn.execute("DELETE FROM pengaturan WHERE kunci = 'password_hash'")  # seperti upload database lama
    conn.commit()
    conn.close()
    c = app.test_client()
    assert "/masuk" in c.get("/").headers["Location"]
    assert c.get("/buat-password").status_code == 302
    assert c.post("/masuk", data={"password": "dari-env-123"}).status_code == 302


def test_kunci_sesi_tetap_setelah_restart(tmp_path, monkeypatch):
    monkeypatch.delenv("USAHA_PASSWORD", raising=False)
    db = str(tmp_path / "s.db")
    a1 = create_app({"DATABASE": db, "TESTING": True})
    a2 = create_app({"DATABASE": db, "TESTING": True})
    assert a1.config["SECRET_KEY"] and a1.config["SECRET_KEY"] == a2.config["SECRET_KEY"]
