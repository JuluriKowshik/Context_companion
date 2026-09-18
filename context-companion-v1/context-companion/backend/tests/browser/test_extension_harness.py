from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[3]
EXTENSION_PATH = ROOT / "extension"


def _install_runtime(page):
    page.set_content(
        """
        <html><body>
          <div id="movie_player">
            <video class="html5-main-video" controls></video>
          </div>
          <script>
            const video = document.querySelector('video');
            Object.defineProperty(video, 'currentTime', {
              get() { return this._time || 0; },
              set(v) { this._time = Number(v); },
              configurable: true,
            });
            Object.defineProperty(video, 'paused', {
              get() { return Boolean(window.__paused); },
              set(v) { },
              configurable: true,
            });
            window.ytInitialPlayerResponse = {
              captions: {
                playerCaptionsTracklistRenderer: {
                  captionTracks: [{ languageCode: 'en', baseUrl: 'http://127.0.0.1:8000/api/timedtext?lang=en' }]
                }
              }
            };
            window.chrome = {
              storage: {
                local: {
                  get: async () => ({ companionEnabled: true, settingsVersion: 3, backendUrl: 'http://127.0.0.1:8000', recentConcepts: {} }),
                  set: async () => {},
                },
                onChanged: { addListener: () => {} },
              },
              runtime: { onMessage: { addListener: () => {} } },
              commands: { onCommand: { addListener: () => {} } },
              tabs: { query: async () => [{ id: 1 }] },
            };
            const makeJsonResponse = (payload) => new Response(JSON.stringify(payload), { status: 200, headers: { 'Content-Type': 'application/json' } });
            const makeTextResponse = (text) => new Response(text, { status: 200, headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
            window.fetch = (input, init) => {
              const url = typeof input === 'string' ? input : (input && input.url) || '';
              if (url.includes('/config')) {
                return Promise.resolve(makeJsonResponse({ auto_show_confidence: 0.85, auto_hint_cooldown_seconds: 8, max_hints_per_minute: 4, prefetch_window_seconds: 6.0, recent_concept_ttl_seconds: 1800, late_display_grace_seconds: 2.5, card_lifetime_seconds: 0.7, max_card_queue_size: 12, max_cards_per_cue: 3 }));
              }
              if (url.includes('/api/timedtext')) {
                return Promise.resolve(makeTextResponse(JSON.stringify({ events: [{ tStartMs: 0, dDurationMs: 2600, segs: [{ utf8: 'The', tOffsetMs: 0 }, { utf8: 'liquidity', tOffsetMs: 150 }, { utf8: 'squeeze', tOffsetMs: 600 }, { utf8: 'is', tOffsetMs: 1000 }, { utf8: 'real', tOffsetMs: 1500 }] }] })));
              }
              if (url.includes('/explain')) {
                return Promise.resolve(makeJsonResponse({ useful: true, title: 'Liquidity', explanation: 'How easily assets can be turned into cash.', source: 'dictionary', normalized_concept: 'liquidity', confidence: 0.92, term: 'liquidity', items: [
                  { title: 'Liquidity', explanation: 'How easily assets can be turned into cash.', source: 'dictionary', normalized_concept: 'liquidity', confidence: 0.92, term: 'liquidity' },
                  { title: 'Squeeze', explanation: 'A sudden shortage of cash or credit.', source: 'dictionary', normalized_concept: 'squeeze', confidence: 0.92, term: 'squeeze' },
                  { title: 'Volatility', explanation: 'How sharply market prices fluctuate.', source: 'dictionary', normalized_concept: 'volatility', confidence: 0.92, term: 'volatility' }
                ] }));
              }
              if (url.includes('/shown')) {
                return Promise.resolve(makeJsonResponse({}));
              }
              return Promise.resolve(makeJsonResponse({}));
            };
          </script>
        </body></html>
        """
    )
    page.add_style_tag(path=str(EXTENSION_PATH / "styles.css"))
    page.add_script_tag(path=str(EXTENSION_PATH / "page-hook.js"))
    page.add_script_tag(path=str(EXTENSION_PATH / "content.js"))
    page.wait_for_timeout(1500)


def test_extension_loads_and_renders_card():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        _install_runtime(page)
        page.evaluate("window.__ccTest.cards.enqueue({title: 'Liquidity', body: 'A sudden shortage of cash.', source: 'dictionary'})")
        page.wait_for_timeout(80)
        card = page.locator('.cc-card').first
        assert card.is_visible()
        text = card.inner_text()
        assert 'liquidity' in text.lower() or 'Dictionary:' in text or 'AI:' in text
        browser.close()


def test_extension_auto_processes_embedded_captions_without_altx():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        _install_runtime(page)
        page.evaluate("window.__ccTest.engine.timeline = { before: () => [], upcoming: () => [], cues: [{ start: 0, end: 3, text: 'The liquidity squeeze is real', index: 0, words: [{ t: 0, text: 'The' }, { t: 0.2, text: 'liquidity' }, { t: 0.7, text: 'squeeze' }, { t: 1.1, text: 'is' }, { t: 1.5, text: 'real' }] }] }; const job = { status: 'done', cue: { start: 0, end: 3, text: 'The liquidity squeeze is real', index: 0 }, result: { useful: true, title: 'Liquidity', explanation: 'How easily assets can be turned into cash.', source: 'dictionary', normalized_concept: 'liquidity', confidence: 0.92, term: 'liquidity', items: [{ title: 'Liquidity', explanation: 'How easily assets can be turned into cash.', source: 'dictionary', normalized_concept: 'liquidity', confidence: 0.92, term: 'liquidity' }] }, showAt: 0.2, readyAt: performance.now(), displayed: false }; window.__ccTest.engine.tryDisplay(job, 0.5);")
        page.wait_for_timeout(150)
        card = page.locator('.cc-card').first
        assert card.is_visible()
        text = card.inner_text()
        assert 'liquidity' in text.lower() or 'Dictionary:' in text or 'AI:' in text
        browser.close()


def test_altx_manual_explain_still_works():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        _install_runtime(page)
        page.evaluate("window.__ccTest.engine.setTimeline([{ start: 0, end: 3, text: 'The liquidity squeeze is real', index: 0, words: [{ t: 0, text: 'The' }, { t: 0.2, text: 'liquidity' }, { t: 0.7, text: 'squeeze' }, { t: 1.1, text: 'is' }, { t: 1.5, text: 'real' }] }]); document.querySelector('video')._time = 1.0; window.__ccTest.engine.videoId='manual-test';")
        page.evaluate("document.dispatchEvent(new KeyboardEvent('keydown', { altKey: true, code: 'KeyX', bubbles: true }))")
        page.wait_for_timeout(200)
        card = page.locator('.cc-card').first
        assert card.is_visible()
        browser.close()


def test_extension_stacks_three_cards_and_removes_in_fifo_order_with_pause():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        _install_runtime(page)
        page.evaluate("['Liquidity', 'Squeeze', 'Volatility'].forEach((title) => window.__ccTest.cards.enqueue({title, body: title, source: 'dictionary'}))")
        page.wait_for_timeout(80)
        cards = page.locator('.cc-card')
        assert cards.count() == 3
        assert cards.all_inner_texts()[0].startswith('Liquidity')
        # Stack nodes are normal-flow flex children, therefore do not overlap.
        boxes = [cards.nth(i).bounding_box() for i in range(3)]
        assert all(boxes[i]['y'] + boxes[i]['height'] <= boxes[i + 1]['y'] for i in range(2))
        page.evaluate('window.__ccTest.cards.pause()')
        page.wait_for_timeout(850)
        assert cards.count() == 3
        page.evaluate('window.__ccTest.cards.resume()')
        page.wait_for_timeout(750)
        assert cards.count() == 2
        assert cards.all_inner_texts()[0].startswith('Squeeze')
        page.wait_for_timeout(750)
        assert cards.count() == 1
        assert cards.all_inner_texts()[0].startswith('Volatility')
        browser.close()


def test_extension_recovery_after_seek():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        _install_runtime(page)
        page.evaluate("window.postMessage({ __cc: true, type: 'REQUEST_EMBEDDED_CAPTIONS' }, '*')")
        page.wait_for_timeout(2000)
        page.evaluate("document.querySelector('video').currentTime = 2.0")
        page.wait_for_timeout(1000)
        page.evaluate("document.querySelector('video').currentTime = 6.0")
        page.wait_for_timeout(1000)
        assert page.locator('.cc-pill').is_visible()
        browser.close()


def test_card_queue_is_bounded_under_a_hundred_event_burst():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        _install_runtime(page)
        page.evaluate("Array.from({length: 100}, (_, i) => window.__ccTest.cards.enqueue({title: `T${i}`, body: 'x', source: 'dictionary'}))")
        page.wait_for_timeout(80)
        cards = page.locator('.cc-card')
        assert cards.count() == 12
        assert cards.all_inner_texts()[0].startswith('T0')
        assert cards.all_inner_texts()[-1].startswith('T11')
        browser.close()
