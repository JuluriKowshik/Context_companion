# Context Companion: Chrome Web Store Publishing Guide

This guide is for productionizing the existing Context Companion extension without changing the current working behavior.

## 1) What is already correct

The project already follows the right architecture for a public Chrome extension:

- the browser extension calls your backend
- the backend calls Groq server-side
- the Groq API key stays off the client
- the extension keeps the YouTube experience lightweight

That means a normal user does not need their own Groq key.

## 2) What must change before publishing

### A. Replace localhost with your real backend URL

The extension currently defaults to a local backend such as:

```text
http://localhost:8000
```

For public use, replace it with your production backend domain, for example:

```text
https://api.example.com
```

This is configured in:

- `context-companion/extension/popup.js`

### B. Remove dev-only host access from the manifest

The extension should not include local dev hosts in the published package.

For public release, the manifest should use the production host and YouTube host only, for example:

```json
"host_permissions": [
  "https://www.youtube.com/*",
  "https://api.example.com/*"
]
```

This is configured in:

- `context-companion/extension/manifest.json`

### C. Add real store metadata

Before submission, prepare:

- extension icon(s)
- screenshots
- description
- privacy policy URL
- support email or contact link

## 3) Production architecture

```text
User
  ↓
Chrome Extension
  ↓
Production Backend API
  ↓
Groq API
```

The Groq secret stays only on the backend server.

## 4) Important security rule

Do not put the Groq API key into:

- extension JavaScript
- `manifest.json`
- bundled frontend code
- client-side environment files
- source maps exposed to users

## 5) Data handling and privacy disclosure

The extension reads YouTube subtitle/caption content and sends it to the backend for contextual explanation.

This means your store listing and privacy policy should say something like:

- the extension analyzes YouTube caption text to identify educational terms
- this data is sent to the backend for processing
- the backend may call an external AI provider to generate explanations
- no users are asked to provide an API key in the extension

If you have a public backend, you should also disclose the following:

- what data is transmitted
- why it is transmitted
- how long it is retained
- whether it is logged
- whether it is shared with third parties

## 6) Minimum necessary permissions

The current extension should use the smallest necessary permissions.

For a public version, you should keep:

- `storage` for local settings
- YouTube host permission for the YouTube page
- backend host permission to call your API

Avoid broad permissions beyond what the extension actually needs.

## 7) Recommended backend protections before public launch

Before publishing, the backend should at least have:

- HTTPS only
- rate limiting
- request validation
- error handling without leaking secrets
- no permissive CORS
- careful logging that omits secrets

## 8) Packaging for submission

Create a ZIP with just the extension folder contents, for example:

```text
ContextCompanion/
  manifest.json
  background.js
  content.js
  page-hook.js
  popup.html
  popup.js
  styles.css
  icons/
  assets/
```

Do not include:

- `.env`
- private keys
- local secrets
- test files
- development logs
- local caches
- `.venv`

## 9) Chrome Web Store submission flow

1. Open the Chrome Web Store developer dashboard
2. Sign in with your Google account
3. Pay the developer registration fee if required
4. Create a new extension item
5. Upload the ZIP
6. Add the store listing details
7. Add screenshots
8. Add privacy policy and support information
9. Submit for review
10. Resolve any policy issues from review
11. Publish when approved

## 10) Good store listing fields

Suggested fields:

- Name: Context Companion
- Category: Productivity or Education
- Description: A lightweight companion that explains useful terms while you watch YouTube videos.
- Screenshots: show the inline card on a video page
- Privacy Policy: add a real webpage or public URL

## 11) Final recommendation

This project does not need a full redesign for Chrome Web Store publishing.

The main tasks are:

- switch the public backend URL
- remove local-dev host permissions
- add privacy policy and store assets
- harden the backend for public access
- submit the packaged extension zip

This keeps the current behavior while making it usable by real users.

## 12) One-sentence summary

A normal user should install the extension and use it without entering a Groq key, because the Groq key stays on your backend server, not in the browser.
