/**
 * API key handling for the Valdo web UI.
 *
 * Loaded before ui.js. Wraps window.fetch so every same-origin /api/ request
 * carries the X-API-Key header. When the server answers 401 (no key) or
 * 403 "Invalid API key", the user is asked for a key once; it is kept in
 * sessionStorage (cleared when the tab closes) and the request is retried.
 *
 * Servers running with API_AUTH_DISABLED=true never return 401, so no prompt
 * is shown there.
 */
(function () {
  'use strict';

  var STORAGE_KEY = 'valdoApiKey';
  var INVALID_KEY_DETAIL = 'Invalid API key';
  var nativeFetch = window.fetch.bind(window);
  var pendingPrompt = null;
  var declined = false;

  /**
   * Read the stored API key, tolerating browsers that block sessionStorage.
   * @returns {string} Stored key, or an empty string.
   */
  function readKey() {
    try { return sessionStorage.getItem(STORAGE_KEY) || ''; } catch (e) { return ''; }
  }

  /**
   * Persist (or clear, when empty) the API key for this browser tab.
   * @param {string} key - API key to store.
   */
  function storeKey(key) {
    try {
      if (key) { sessionStorage.setItem(STORAGE_KEY, key); } else { sessionStorage.removeItem(STORAGE_KEY); }
    } catch (e) { /* storage unavailable: key lives only in memory */ }
    window._apiKey = key || undefined;
  }

  /**
   * Return true when the request targets this server's /api/ routes.
   * @param {RequestInfo} input - fetch() input.
   * @returns {boolean}
   */
  function isApiRequest(input) {
    try {
      var url = new URL(input instanceof Request ? input.url : String(input), window.location.href);
      return url.origin === window.location.origin && url.pathname.indexOf('/api/') === 0;
    } catch (e) {
      return false;
    }
  }

  /**
   * Build fetch init options carrying the API key.
   * @param {RequestInfo} input - fetch() input.
   * @param {RequestInit} init - Caller's init options.
   * @param {string} key - API key to send.
   * @param {boolean} override - Replace a key the caller already set.
   * @returns {RequestInit}
   */
  function withKey(input, init, key, override) {
    var opts = Object.assign({}, init || {});
    var headers = new Headers(opts.headers || (input instanceof Request ? input.headers : undefined));
    if (key && (override || !headers.get('X-API-Key'))) {
      headers.set('X-API-Key', key);
    }
    opts.headers = headers;
    return opts;
  }

  /**
   * Ask the user for an API key, sharing one prompt across concurrent requests.
   * @returns {Promise<string>} Entered key, or an empty string if declined.
   */
  function askForKey() {
    if (declined) { return Promise.resolve(''); }
    if (!pendingPrompt) {
      pendingPrompt = Promise.resolve().then(function () {
        var entered = window.prompt('This Valdo server requires an API key. Enter your API key:') || '';
        entered = entered.trim();
        if (entered) { storeKey(entered); } else { declined = true; }
        pendingPrompt = null;
        return entered;
      });
    }
    return pendingPrompt;
  }

  /**
   * Return true when the response means the key is missing or wrong.
   * @param {Response} resp - Server response.
   * @returns {Promise<boolean>}
   */
  function needsKey(resp) {
    if (resp.status === 401) { return Promise.resolve(true); }
    if (resp.status !== 403) { return Promise.resolve(false); }
    return resp.clone().json()
      .then(function (body) { return body && body.detail === INVALID_KEY_DETAIL; })
      .catch(function () { return false; });
  }

  window._apiKey = readKey() || undefined;

  window.fetch = function (input, init) {
    if (!isApiRequest(input)) { return nativeFetch(input, init); }
    var sentKey = window._apiKey || '';
    return nativeFetch(input, withKey(input, init, sentKey, false)).then(function (resp) {
      return needsKey(resp).then(function (missing) {
        if (!missing) { return resp; }
        // Another request may already have obtained a newer key; reuse it without prompting.
        if (window._apiKey && window._apiKey !== sentKey) {
          return nativeFetch(input, withKey(input, init, window._apiKey, true));
        }
        if (sentKey) { storeKey(''); }
        return askForKey().then(function (key) {
          return key ? nativeFetch(input, withKey(input, init, key, true)) : resp;
        });
      });
    });
  };
})();
