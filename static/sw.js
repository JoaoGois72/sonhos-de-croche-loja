self.addEventListener("install", function(event) {
  event.waitUntil(
    caches.open("croche-store").then(function(cache) {
      return cache.addAll([
        "/",
        "/static/css/premium.css"
      ]);
    })
  );
});

self.addEventListener("fetch", function(event) {
  event.respondWith(
    caches.match(event.request).then(function(response) {
      return response || fetch(event.request);
    })
  );
});