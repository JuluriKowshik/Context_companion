# Context Companion

A quiet companion for YouTube. When a video provides an embedded caption track, it reads that track automatically—even when captions are not visibly enabled—and shows a short explanation only for high-value terms.

## Current implementation notes

This revision keeps the baseline’s local-first, high-recall behavior but hardens the lexical pipeline:

- subtitle tokenization preserves valid lexical units such as contractions, hyphenated compounds and abbreviations while rejecting punctuational fragments
- candidate generation uses Zipf frequency as a signal rather than a hard-coded final rule
- token correctness is validated before a term reaches dictionary lookup or LLM evaluation
- classifier decisions are configurable and logged with reason codes
- the benchmark suite covers common, rare, technical, and borderline vocabulary

## How it works (v0.3)

```
YouTube player fetches its caption track (when CC is on)
  -> page-hook.js observes that response, hands the timed cues to content.js
  -> Timeline: every cue with start/end times
  -> Prefetcher: for cues within the look-ahead window, run the pipeline early
  -> backend POST /explain
       1. bundled concepts (235 curated, alias index, ~50 microseconds)
       2. learned concepts (SQLite, loaded into the same index)
       3. session memory: already shown? already defined by the video itself?
       4. classifier gate (skipped for manual Alt+X)
       5. LLM (Gemini or Grok, selected in .env), result cached to SQLite
  -> result waits in the extension until the word's timestamp arrives
  -> display policy decides: confidence, cooldown, per-minute cap, not shown before
  -> card shows at the moment the term is spoken; extension reports it via POST /shown
```

The Companion state (on/off) lives in `chrome.storage.local`, so it survives navigation between videos, page refreshes, and browser restarts. It stays on until you switch it off, from the pill inside the player or from the popup.

### What you see

Two things inside the player, both bottom-right, both translucent: a pill reading `Companion ON` (green dot) or `OFF` (red dot) that fades with YouTube's own controls, and, only when something is worth explaining, a card with the term on one line and the meaning below. No inspector, no cue lists, no chat.

### Multi-card queue

`POST /explain` now returns an `items` array (up to three final-eligible items) while retaining the original top-level first item for older extensions. Local concept matches preserve subtitle occurrence order; a maximum of three is kept per cue after normal candidate, context, confidence, and duplicate checks. The extension renders them as a fixed-width vertical stack.

The global card queue is capped at 12 cards; overflow deterministically retains earlier cards. A single timer belongs only to the queue head: it is removed after the configured five-second lifetime, then the next head gets its five seconds. This guarantees FIFO removal even for simultaneous results. Playback pause freezes the head timer; resume continues its remaining time. Seek and video navigation clear cards and abort/invalidate old requests, so late responses cannot populate a new context.

### Why it stays quiet

The display policy in `content.js` (`DisplayPolicy`) applies, in order: the backend must say useful; the concept must not have been shown in this video; not shown in any video within the last 30 minutes; confidence at or above 0.85; at least 8 seconds since the last card; at most 4 cards per minute. All thresholds come from `.env` via `GET /config`. Every decision, shown or suppressed, is logged with its reason.

### Word-level timing

Auto-generated caption tracks carry a timestamp per word. When they do, the card fires at the word, not the line. A result that arrives after the line has ended plus a short grace period (2.5 seconds by default) is dropped rather than shown late.

If the caption track is not captured (live streams, hook installed after the page loaded), the extension falls back to reading captions from the DOM as they appear. The pipeline still runs and the card still shows while the line is on screen; it just cannot run ahead.

### The no-spoiler rule

For a cue at time T, the context sent to the backend contains only cues with start <= T. Prefetching may run before T. Nothing is displayed before T. This is enforced in one function, `Prefetcher.contextFor()` in `content.js`, and mirrored in the backend session store, which only consults cues recorded with a timestamp strictly before the cue being explained.

### Why not a full English dictionary

Almost no English words are worth interrupting a viewer for. A giant dictionary costs memory and produces false positives ("stroke of genius") while helping almost nothing. Instead: a few hundred curated concepts with aliases, matched by scanning 1 to 4 word n-grams against an in-memory index, plus an SQLite cache of whatever the LLM has taught us. The LLM handles the long tail.

## Layout

```
extension/
  manifest.json      MV3; page-hook.js in MAIN world at document_start
  page-hook.js       observes the player's /api/timedtext response
  content.js         Engine (prefetch + timed display), DisplayPolicy, Pill, Card, live fallback
  popup.html/js      master switch, backend URL, provider status
backend/
  app/
    main.py                     app wiring, pooled HTTP client
    config.py                   .env settings
    routes/explain.py           POST /explain, POST /shown, GET /config, GET /health, GET /stats
    schemas/explain.py          request/response, Timings
    data/concepts/*.json        bundled knowledge by domain
    services/
      textnorm.py               normalisation, n-grams, cheap stemming
      knowledge/index.py        ConceptIndex: alias -> concept, n-gram lookup
      learned_cache.py          SQLite persistence for LLM-learned concepts
      session_store.py          per-video memory, "already explained" detection
      classifier.py             rule-based candidate gate
      explain_service.py        the pipeline, timings, in-flight dedupe, retry
      providers/                LLMProvider, GeminiProvider, GrokProvider, MockProvider
  requirements.txt
  .env.example
```

## Setup

### 1. Backend

Python 3.10 or newer (3.14 works; the pins are minimum versions with prebuilt wheels).

Use this exact sequence in PowerShell from the project root:

```powershell
cd "C:\Users\Kowshik.Juluri\Downloads\context-companion-v1\context-companion"
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-dev.txt
copy .env.example .env
```

Then edit the backend `.env` file and set at least one provider key:

```env
LLM_PROVIDER=groq
GROQ_API_KEY=your_key_here
# or:
# LLM_PROVIDER=gemini
# GEMINI_API_KEY=your_key_here
```

### 2. Start the backend

From inside `backend/`:

```powershell
cd "C:\Users\Kowshik.Juluri\Downloads\context-companion-v1\context-companion\backend"
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Check the API is alive:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/health
```

You should see `ok: True` and a provider/model value, plus `bundled_concepts` loaded.

### 3. Extension

Open Chrome and load the unpacked extension:

`chrome://extensions` → Developer mode → Load unpacked → pick `context-companion/extension/`

Then refresh a YouTube tab and keep captions enabled (or use the embedded caption path that the extension listens for).

### Minimal command list to run it

If you want the shortest copy-paste checklist, this is the full sequence:

```powershell
cd "C:\Users\Kowshik.Juluri\Downloads\context-companion-v1\context-companion\backend"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-dev.txt
copy .env.example .env
# edit .env and add your API key
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Then in another terminal:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/health
```

On first start, the backend builds `data/wordnet_dictionary.db` from the
bundled NLTK WordNet data. This powers offline definitions for uncommon words;
the curated concept JSON files continue to handle domain phrases and references.

### 2. Extension

`chrome://extensions` → Developer mode → Load unpacked → pick `extension/`. If an older version is loaded, click its reload arrow, then refresh open YouTube tabs.

### 3. Use it

1. Open a captioned YouTube video.
2. Keep **Embedded-caption explanations** enabled in the popup (it is on by default). YouTube captions do not have to be visible.
3. The card identifies a local definition as *Dictionary:* and a contextual model answer as *AI:*.
4. Open another video and the old subtitle context is discarded.

Press F12 and open Console to see what the Companion is doing. Each cue that reaches a decision logs one line:

```
shown            cue@84.20 show@84.84 "They're shorting the housing market." | short selling src=bundled conf=0.95 | knowledge 0.1ms session 0ms classifier 0ms llm 0ms net 6ms | ready 5.3s early
cooldown         cue@88.10 show@88.10 "The banks were highly leveraged"      | leverage src=bundled conf=0.95 | ...
not_useful       cue@91.40 show@91.40 "Come on, let's go."                    | - src=classifier conf=- | ...
```

`show@` is the word-aligned time. `ready Ns early` tells you whether the look-ahead had enough room for the model.

### Testing the backend alone (PowerShell)

Create `backend/test.json`:

```json
{"current_subtitle": "They are shorting the housing market.", "context": [], "force": false, "video_id": "test", "cue_start": 10}
```

```powershell
Invoke-RestMethod -Uri http://localhost:8000/explain -Method Post -ContentType "application/json" -InFile test.json
Invoke-RestMethod -Uri http://localhost:8000/config
```

### Tests and coverage

Run from `backend/` with the virtual environment active:

```powershell
python -m coverage run -m pytest tests -q
python -m coverage report -m
```

Expect `source: bundled`, `confidence: 0.95`, `total_ms` under 1, and the config endpoint echoing your `.env` thresholds.

## Latency: what was wrong and what changed

| Cause | Fix |
|---|---|
| Gemini 3 models think before answering; default level is high, we never set one | `GEMINI_THINKING_LEVEL=minimal`, sent as `thinkingConfig.thinkingLevel` |
| Every explanation waited for a keypress before any work started | Prefetcher runs the pipeline up to N seconds ahead using the captured timeline |
| Every request went through the service worker, which Chrome suspends | Content script calls the backend directly; also enables abort on seek |
| Known terms went to the LLM every time | Bundled index + SQLite learned cache answer in well under a millisecond |
| Same cue explained twice if prefetch and Alt+X raced | In-flight deduplication in `explain_service.py` |
| New `httpx.AsyncClient` per call | One pooled client for the process |

## Switching providers

`.env`: `LLM_PROVIDER=grok` and `GROK_API_KEY=...`. Restart uvicorn. Nothing else changes. To add a provider, subclass `LLMProvider` in `services/providers/` and register it in `factory.py`.

## Troubleshooting

**Console says "live captions active" and never "timeline ready".** The hook did not see the caption request. Toggle CC off and on. If the video is a live stream, there is no track to capture and the DOM fallback is the only option.

**Card says "Model request failed".** Run the PowerShell test above; the response includes `error_detail` with the provider's HTTP status. 404 means the model name is retired, 400/401/403 means a key problem.

**Pill is not visible.** Move the mouse over the player; the pill hides together with YouTube's controls. If it never appears, the extension did not load on this page: check `chrome://extensions` for errors and refresh.

**Too many cards.** Raise `AUTO_SHOW_CONFIDENCE` or `AUTO_HINT_COOLDOWN_SECONDS` in `.env`; the extension picks the new values up on next page load. **Too few.** Check the console for `low_confidence_` and `cooldown` verdicts to see which rule is suppressing.

**Wrong or stale subtitle in live mode.** The DOM selectors live in `LiveDomSource.read()`. Inspect the caption element and update `.caption-visual-line` / `.ytp-caption-segment` if YouTube changed them.

**A bundled explanation is wrong or a term misfires.** Edit the JSON in `backend/app/data/concepts/`. Set `"match_name": false` for a concept whose bare name is ambiguous; add `"block_next": ["of"]` to veto a match when a specific word follows it.

## What is deliberately not here

Auth, accounts, cloud databases, embeddings or vector search, other streaming platforms, an ML classifier, voice, vision, future-subtitle context. Alt+X remains as an undocumented debugging shortcut that explains the line on screen regardless of policy; it is not part of the product.

## Next experiments

1. Log a week of `source=` values. What fraction of Alt+X presses hit bundled, learned, or llm? That number decides whether to grow the bundled set or trust the cache.
2. Sweep the look-ahead window (4, 6, 8, 10) against your provider's `llm_ms` distribution. The right window is roughly p90 of `llm_ms` plus one second.
3. Watch three full videos with the Companion on and count cards you did not want. Above one per ten minutes means tightening the policy or the classifier, not adding features.
4. Spoiler audit: for 30 random cues, dump the `context` array the extension sends and confirm every `timestamp <= cue_start`.
5. Compare Gemini and Grok on the same 50 cues: `llm_ms`, useful rate, and how often the two disagree.
