from tests.test_auth import app_login  # noqa: F401  (fixture)


def test_manifest_dan_service_worker_bisa_diakses_tanpa_login(app_login):  # noqa: F811
    c = app_login.test_client()
    m = c.get("/manifest.webmanifest")
    assert m.status_code == 200
    assert m.mimetype == "application/manifest+json"
    data = m.get_json()
    assert data["display"] == "standalone"
    assert {i["sizes"] for i in data["icons"]} >= {"192x192", "512x512"}
    for ikon in data["icons"]:
        assert c.get(ikon["src"]).status_code == 200

    sw = c.get("/sw.js")
    assert sw.status_code == 200
    assert sw.headers["Service-Worker-Allowed"] == "/"
    assert c.get("/static/offline.html").status_code == 200


def test_halaman_memuat_manifest(client):
    teks = client.get("/").get_data(as_text=True)
    assert 'rel="manifest"' in teks and "serviceWorker" in teks
