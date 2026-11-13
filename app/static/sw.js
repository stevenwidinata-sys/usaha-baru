// Service worker: aplikasi bisa dipasang di HP. Data selalu diambil langsung dari server (tidak disimpan
// di HP), hanya halaman "tidak ada internet" yang disimpan supaya muncul pesan yang jelas saat offline.
var CACHE = 'usaha-baru-v1';
var OFFLINE = '/static/offline.html';

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) {
    return c.addAll([OFFLINE, '/static/ikon/ikon-192.png']);
  }));
  self.skipWaiting();
});

self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }));
  self.clients.claim();
});

self.addEventListener('fetch', function (e) {
  if (e.request.mode !== 'navigate') return;
  e.respondWith(fetch(e.request).catch(function () { return caches.match(OFFLINE); }));
});
