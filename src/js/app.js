/**
 * Stremio launcher for webOS TV.
 *
 * Shows a boot screen, confirms the TV can reach Stremio, then opens it.
 *
 * ES5 only -- see config.js.
 */
(function () {
  'use strict';

  var cfg = window.STREMIO_CONFIG;

  var KEY_ENTER = 13;

  var el = {
    status: document.getElementById('status'),
    error: document.getElementById('error'),
    errorTitle: document.getElementById('error-title'),
    errorBody: document.getElementById('error-body'),
    errorKeys: document.getElementById('error-keys')
  };

  var launched = false;  // guards against opening twice
  var bootDeadline = 0;  // earliest time we may leave the boot screen

  /**
   * Stremio's engine is compiled to WebAssembly, which Chromium only gained in
   * 57. Report that plainly rather than opening a page that can never load.
   */
  function hasWebAssembly() {
    return typeof window.WebAssembly === 'object' &&
           typeof window.WebAssembly.instantiate === 'function';
  }

  /**
   * Probe with an <img>: image loads are not subject to CORS, and fetch() does
   * not exist on the oldest firmware this supports.
   */
  function probe(url, timeoutMs, done) {
    var img = new Image();
    var settled = false;

    function finish(ok) {
      if (settled) return;
      settled = true;
      img.onload = img.onerror = null;
      done(ok);
    }

    img.onload = function () { finish(true); };
    img.onerror = function () { finish(false); };
    window.setTimeout(function () { finish(false); }, timeoutMs);

    // Cache-bust so a cached response cannot mask a dead network.
    img.src = url + (url.indexOf('?') === -1 ? '?' : '&') + 'cb=' + (new Date()).getTime();
  }

  function setStatus(text) {
    el.status.textContent = text;
  }

  function showError(title, body, keys) {
    el.errorTitle.textContent = title;
    el.errorBody.textContent = body;
    el.errorKeys.textContent = keys || '';
    el.error.hidden = false;
    setStatus('');
  }

  function launch() {
    if (launched) return;
    launched = true;
    setStatus('Opening Stremio…');

    // Two details here are load-bearing, so do not turn this into an embed:
    //
    // Navigating the top-level window makes Stremio's own origin first-party,
    // which is what lets it keep your login and addon collection across
    // launches. Loading it into a frame instead would make that storage
    // third-party, and webOS discards it -- you would be signed out every time.
    //
    // replace() rather than assign() keeps the boot screen out of session
    // history, so Back from Stremio's home screen exits the app cleanly.
    window.location.replace(cfg.url);
  }

  function probeUrl() {
    var base = cfg.url.charAt(cfg.url.length - 1) === '/' ? cfg.url : cfg.url + '/';
    return base + cfg.probeImage;
  }

  function beginProbe() {
    el.error.hidden = true;
    setStatus('Connecting…');

    probe(probeUrl(), cfg.probeTimeoutMs, function (ok) {
      if (ok) {
        // Hold briefly so the boot screen reads as a splash, not a flash.
        window.setTimeout(launch, Math.max(0, bootDeadline - (new Date()).getTime()));
        return;
      }

      // Fail open. The check is a diagnostic, not a gate: a blocked CDN or a
      // slow lookup must never stop the app from opening. If the TV really is
      // offline, the error that follows is at least the accurate one.
      showError(
        'Trouble reaching Stremio',
        'The connection check did not succeed. Opening Stremio anyway; if the ' +
        'TV is offline you will see a network error.',
        'Press OK to continue now'
      );
      window.setTimeout(launch, cfg.failOpenMs);
    });
  }

  // OK dismisses any notice and proceeds immediately.
  document.addEventListener('keydown', function (event) {
    if (launched || el.error.hidden) return;
    if ((event.keyCode || event.which) === KEY_ENTER) {
      event.preventDefault();
      launch();
    }
  }, true);

  function init() {
    bootDeadline = (new Date()).getTime() + cfg.minBootMs;

    if (!hasWebAssembly()) {
      showError(
        'This TV is not supported',
        'Stremio needs WebAssembly, which this webOS version does not provide. ' +
        'webOS 5.0 or newer is required.',
        'Press OK to try anyway'
      );
      return;
    }

    beginProbe();
  }

  init();
})();
