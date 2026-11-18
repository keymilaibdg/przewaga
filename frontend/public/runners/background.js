// Background check of the Android app (@capacitor/background-runner, outside the web view).
// Every ~2 hours: download meta.json published by the pipeline and show notifications the user has not seen.
// The app passes the data address and the notification settings with the "configure" event.
// Runner environment: fetch, CapacitorKV, CapacitorNotifications, console; no DOM, no app storage.

var KIND_SETTING = { new_value: "newValue", withdrawn: "withdrawn", odds_move: "oddsMove", lineup: "lineups", settled: "settled" };
var MAX_PER_RUN = 4;
var MAX_AGE_MS = 36 * 3600 * 1000;

function kvGet(key) {
  try {
    var r = CapacitorKV.get(key);
    var v = r && typeof r === "object" ? r.value : r;
    return v === undefined || v === null || v === "" ? null : v;
  } catch (e) {
    return null;
  }
}

function kvGetJson(key, fallback) {
  var v = kvGet(key);
  if (v === null) return fallback;
  try {
    return JSON.parse(v);
  } catch (e) {
    return fallback;
  }
}

function notifId(s) {
  var h = 0;
  for (var i = 0; i < s.length; i++) h = (Math.imul(31, h) + s.charCodeAt(i)) | 0;
  return 1 + (Math.abs(h) % 900000);
}

addEventListener("configure", function (resolve, reject, args) {
  try {
    if (args && args.dataUrl) CapacitorKV.set("dataUrl", String(args.dataUrl));
    if (args && args.notifications) CapacitorKV.set("settings", JSON.stringify(args.notifications));
    resolve();
  } catch (e) {
    reject(e);
  }
});

addEventListener("checkData", function (resolve, reject) {
  var base = kvGet("dataUrl");
  if (!base) {
    resolve(); // the app has not been opened yet
    return;
  }
  var settings = kvGetJson("settings", {});
  var seen = kvGetJson("seen", null);
  var first = seen === null;
  seen = seen || [];
  fetch(base + "/meta.json?t=" + Math.floor(Date.now() / 300000))
    .then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    })
    .then(function (meta) {
      var items = (meta && meta.notifications) || [];
      var now = Date.now();
      var fresh = [];
      for (var i = 0; i < items.length; i++) {
        var n = items[i];
        if (seen.indexOf(n.id) >= 0) continue;
        seen.push(n.id);
        if (first) continue; // first run: remember what exists, do not flood the user
        var key = KIND_SETTING[n.kind];
        if (key && settings[key] === false) continue;
        if (now - Date.parse(n.at) > MAX_AGE_MS) continue;
        fresh.push(n);
      }
      var toShow = fresh.slice(0, MAX_PER_RUN).map(function (n) {
        return { id: notifId(n.id), title: n.title, body: n.body, scheduleAt: new Date(Date.now() + 1000) };
      });
      if (fresh.length > MAX_PER_RUN) {
        toShow.push({ id: notifId("more-" + now), title: "Przewaga", body: "Nowe powiadomienia: " + (fresh.length - MAX_PER_RUN) + " więcej w aplikacji.", scheduleAt: new Date(Date.now() + 1000) });
      }
      if (toShow.length) CapacitorNotifications.schedule(toShow);
      CapacitorKV.set("seen", JSON.stringify(seen.slice(-300)));
      CapacitorKV.set("lastCheck", new Date().toISOString());
      resolve();
    })
    .catch(function (e) {
      console.warn("przewaga background check failed: " + e);
      resolve(); // offline: try again next time
    });
});
