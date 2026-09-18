// Public production value should be replaced with your deployed backend hostname.
// Example: https://api.yourdomain.com
const DEFAULTS = { companionEnabled: true, backendUrl: "https://api.yourdomain.com" };
const $ = (id) => document.getElementById(id);

async function load() {
  const s = { ...DEFAULTS, ...(await chrome.storage.local.get(DEFAULTS)) };
  $("enabled").checked = s.companionEnabled;
  $("backendUrl").value = s.backendUrl;
  $("stateLabel").textContent = s.companionEnabled ? "Embedded-caption explanations are on" : "Embedded-caption explanations are off";
  checkHealth(s.backendUrl);
}

async function save() {
  const backendUrl = $("backendUrl").value.trim().replace(/\/+$/, "") || DEFAULTS.backendUrl;
  const companionEnabled = $("enabled").checked;
  await chrome.storage.local.set({ backendUrl, companionEnabled });
  $("stateLabel").textContent = companionEnabled ? "Embedded-caption explanations are on" : "Embedded-caption explanations are off";
  checkHealth(backendUrl);
}

async function checkHealth(url) {
  const el = $("status");
  el.className = "status"; el.textContent = "Checking backend…";
  try {
    const data = await (await fetch(`${url}/health`)).json();
    el.className = "status ok";
    el.textContent = data.model_configured
      ? `Backend online: ${data.provider} (${data.model}), ${data.bundled_concepts} local concepts`
      : "Backend online, no LLM key set. Mock mode.";
  } catch {
    el.className = "status bad";
    el.textContent = "Backend not reachable. Start it with uvicorn and check the URL.";
  }
}

$("enabled").addEventListener("change", save);
$("backendUrl").addEventListener("change", save);
load();
