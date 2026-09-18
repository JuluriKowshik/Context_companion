# Context Companion Production Deployment Checklist

This checklist is for moving the existing Context Companion backend to a public, secure HTTPS host without changing the working extension behavior.

## 1) Confirm the architecture is still correct

The extension is already designed to call your backend, not Groq directly.

Production flow:

```text
Chrome Extension
  -> HTTPS backend API
  -> Groq API (server-side secret)
```

This matches the current code structure and keeps the Groq key off the client.

## 2) Choose the real API host

Before deployment, decide your public domain, for example:

```text
https://api.yourdomain.com
```

Do not ship a public extension with a local development URL.

Update the default value in:

- `context-companion/extension/popup.js`

The current placeholder is:

```js
const DEFAULTS = { companionEnabled: true, backendUrl: "https://api.example.com" };
```

Replace it with your real host before packaging the extension.

## 3) Deploy the backend to a secure host

Use a host that supports:

- HTTPS by default
- environment variables / secret management
- automatic restarts
- health checks
- logs
- stable domain names

Examples of acceptable deployment targets:

- Render
- Railway
- Fly.io
- Azure App Service
- Google Cloud Run
- AWS Elastic Beanstalk
- a managed VM / container service

## 4) Configure backend secrets

Set the following in the server environment, not in the extension:

```env
LLM_PROVIDER=groq
GROQ_API_KEY=your_server_secret
GROQ_MODEL=groq/compound
```

Also keep the following private:

- API keys
- model keys
- database files if generated locally
- debug logs with request payloads

## 5) Check the backend startup path

Your backend should run with an app server such as Uvicorn or a managed equivalent.

Example:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Verify the health endpoint publicly:

```bash
curl https://api.yourdomain.com/health
```

It should return success status and backend metadata.

## 6) Harden CORS for production

The app already contains CORS configuration. In production, do not leave it permissive.

In `backend/app/main.py` the code is currently using a settings-driven list of origins. Keep it limited to:

- your production backend domain
- your extension origin pattern if needed
- YouTube only if absolutely required by your design

Do not use a broad wildcard in public production unless you are deliberately accepting all origins and can justify it.

## 7) Protect the public API

Before releasing publicly, add at least:

- request validation
- rate limiting
- abuse guard against repeated calls
- timeout safeguards
- logging without leaking secrets
- strict error handling

This matters because `/explain` is a public AI endpoint and can be abused if not protected.

## 8) Validate the extension against the real backend

After deployment, test the extension against the public API with the same behavior as local testing:

- YouTube captions load normally
- backend `/health` responds
- `/config` returns display policy values
- `/explain` responds with a valid result
- cards appear at the right time
- no UI breakage

## 9) Replace the placeholder URL in the extension

After the backend is live:

- update the popup default backend URL
- keep the user-editable field for convenience
- publish the extension with the real default URL

The goal is to maintain the same experience while avoiding a manual setup step for users.

## 10) Final public-release package check

Before uploading to the Chrome Web Store, confirm:

- no `.env` file is inside the ZIP
- no API keys are inside extension files
- no localhost references remain in production files
- no dev-only testing infrastructure remains
- the extension package contains only the needed files
- the backend is reachable securely over HTTPS

## 11) Production test checklist

Perform these checks after deployment:

- extension installs cleanly
- popup shows backend online
- extension works on YouTube pages
- no console errors caused by missing backend
- request timeouts are handled gracefully
- backend failures do not crash the page
- queue behavior stays stable under repeated cues
- repeated playback does not leak memory or duplicate cards

## 12) Stress testing summary

This cannot be fully replaced by code inspection alone. A realistic production test should include:

- open multiple YouTube tabs
- switch videos quickly
- enable/disable extension repeatedly
- trigger many subtitle cues quickly
- simulate backend delay/failure
- verify the card queue still behaves correctly

Do not call the app production-ready without these checks.

## 13) Final green-light rule

The deployment is ready only if all of these are true:

- HTTPS backend is live
- Groq key is only on the server
- extension points to the real backend
- no secrets are in the browser package
- the extension behavior remains the same as local testing
- rate limiting and request validation are in place

## 14) Final note

The backend should be treated as a private service. The extension is the public-facing product, and it should not expose service credentials.
