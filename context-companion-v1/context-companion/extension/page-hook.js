// Runs in the page's MAIN world at document_start, before YouTube's player.
//
// Purpose: hand an embedded caption track to the content script. We use the
// signed base URL supplied by YouTube's player response, so captions need not
// be visibly enabled in YouTube's UI.
(() => {
  if (window.__ccHookInstalled) return;
  window.__ccHookInstalled = true;

  const isTimedText = (url) => typeof url === "string" && url.includes("/api/timedtext");

  const emit = (url, body) => {
    if (!body) return;
    window.postMessage({ __cc: true, type: "TIMEDTEXT", url, body, at: performance.now() }, location.origin);
  };

  let requested = false;
  async function fetchEmbeddedTrack() {
    if (requested) return;
    const tracks = window.ytInitialPlayerResponse?.captions?.playerCaptionsTracklistRenderer?.captionTracks || [];
    if (!tracks.length) return;
    requested = true;
    const language = (navigator.language || "").toLowerCase();
    const track = tracks.find((item) => language.startsWith((item.languageCode || "").toLowerCase())) || tracks[0];
    try {
      const url = track.baseUrl + (track.baseUrl.includes("?") ? "&" : "?") + "fmt=json3";
      const response = await originalFetch(url);
      emit(url, await response.text());
    } catch (_) { requested = false; }
  }

  window.addEventListener("message", (event) => {
    if (event.source !== window || event.data?.__cc !== true || event.data.type !== "REQUEST_EMBEDDED_CAPTIONS") return;
    // YouTube may populate the player response shortly after navigation.
    let attempts = 0;
    const tryFetch = () => {
      fetchEmbeddedTrack();
      if (!requested && ++attempts < 20) setTimeout(tryFetch, 250);
    };
    tryFetch();
  });

  // fetch()
  const originalFetch = window.fetch;
  window.fetch = function (input, init) {
    const promise = originalFetch.apply(this, arguments);
    try {
      const url = typeof input === "string" ? input : input && input.url;
      if (isTimedText(url)) {
        promise.then((res) => res.clone().text().then((body) => emit(url, body)).catch(() => {})).catch(() => {});
      }
    } catch (_) {}
    return promise;
  };

  // XMLHttpRequest
  const originalOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (method, url) {
    this.__ccUrl = typeof url === "string" ? url : String(url);
    return originalOpen.apply(this, arguments);
  };
  const originalSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.send = function () {
    if (isTimedText(this.__ccUrl)) {
      this.addEventListener("load", () => {
        try {
          let body = "";
          if (this.responseType === "" || this.responseType === "text") body = this.responseText;
          else if (this.responseType === "json") body = JSON.stringify(this.response);
          else if (this.responseType === "arraybuffer") body = new TextDecoder().decode(this.response);
          emit(this.__ccUrl, body);
        } catch (_) {}
      });
    }
    return originalSend.apply(this, arguments);
  };
})();
