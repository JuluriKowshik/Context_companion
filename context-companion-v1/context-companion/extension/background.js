// Chrome-command path for Alt+X. content.js also has a keydown fallback for
// cases where Chrome has not assigned the command on a platform.
chrome.commands.onCommand.addListener(async (command) => {
  if (command !== "explain-current-subtitle") return;
  const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  if (tab?.id) chrome.tabs.sendMessage(tab.id, { type: "CC_EXPLAIN_NOW" }).catch(() => {});
});
