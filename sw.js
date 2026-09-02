/* study-offline v1.1 — service worker (synced: hyrox/cscs).
   Self-configuring: cache name derives from the registration scope path, so
   the two study sites on the shared github.io origin never collide.
   Strategy: landing pages (index.html, the bare scope root, and the rolling
   *_today.html copies) = network-first with revalidation — their resume
   redirect must stay fresh online but still work from cache offline;
   everything else same-site = cache-first with background refresh.
   Fetches made with cache:"no-store" (the offline-pack downloader) pass
   straight through to the network so the pack can never restore stale copies
   of itself. The pack is written into the SAME cache by the page. */
"use strict";
var SCOPE = self.registration.scope;
var SITE = (new URL(SCOPE).pathname.replace(/[^a-z0-9]/gi, "") || "root");
var CACHE = "svoff-" + SITE + "-v1"; /* stable across sw updates — never wipe the pack */

self.addEventListener("install", function () { self.skipWaiting(); });
self.addEventListener("activate", function (e) {
  e.waitUntil((async function () {
    var keys = await caches.keys();
    await Promise.all(keys.filter(function (k) {
      return k.indexOf("svoff-" + SITE + "-") === 0 && k !== CACHE;
    }).map(function (k) { return caches.delete(k); }));
    await self.clients.claim();
  })());
});

function keyFor(url) { return url.split("#")[0].split("?")[0]; }
/* "index" = the scope root or index.html (one canonical cache key — a bare
   directory navigation and the packed "index.html" entry must converge).
   "today" = the rolling *_today.html landing copy (same redirect, but its OWN
   key — it lives in daily/ and its relative links differ from index.html). */
function landingKind(url) {
  var p = new URL(url).pathname, sp = new URL(SCOPE).pathname;
  if (p === sp || p === sp + "index.html") return "index";
  if (p.slice(-11) === "_today.html") return "today";
  return "";
}

self.addEventListener("fetch", function (e) {
  var req = e.request;
  if (req.method !== "GET") return;
  if (req.cache === "no-store") return; /* pack downloader: straight to network */
  /* Request.cache is undefined on Safari < 16.4, where the test above silently
     fails open and the build stamp would be cached BY the very cache it exists
     to audit (and the pack downloader would re-store pages it already had).
     Bypass these two by path as well, so the guarantee holds on every engine. */
  if (/\/data\/(build|pages)\.json$/.test(req.url.split("#")[0].split("?")[0])) return;
  if (req.url.indexOf(SCOPE) !== 0) return; /* other origins + the sibling site: untouched */
  var key = keyFor(req.url);
  if (key.slice(-6) === "/sw.js") return;   /* let the browser manage sw updates itself */
  e.respondWith((async function () {
    var cache = await caches.open(CACHE);
    var kind = landingKind(req.url);
    if (kind) {
      var ck = kind === "index" ? new URL("index.html", SCOPE).href : key;
      try {
        /* plain URL fetch: never fetch(req, init) on a navigation Request
           (throws); no-cache forces conditional revalidation past the
           10-minute GitHub Pages HTTP cache. */
        var r = await fetch(req.url, { cache: "no-cache", credentials: "same-origin" });
        if (r && r.ok && !r.redirected) cache.put(ck, r.clone()).catch(function () {});
        return r;
      } catch (err) {
        var hit = await cache.match(ck);
        if (hit) return hit;
        throw err;
      }
    }
    var hit2 = await cache.match(key);
    var refresh = fetch(req).then(function (r) {
      if (r && r.ok && !r.redirected && r.type === "basic")
        cache.put(key, r.clone()).catch(function () {});
      return r;
    }).catch(function () { return null; });
    if (hit2) { refresh.catch(function () {}); return hit2; }
    var net = await refresh;
    if (net) return net;
    return new Response(
      "Offline — this page isn't stored on this device yet.\n" +
      "Reconnect once, open the site, and tap \"Download all\" in the listen panel.",
      { status: 503, headers: { "Content-Type": "text/plain; charset=utf-8" } });
  })());
});
