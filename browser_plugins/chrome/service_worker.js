const API_BASE = "http://127.0.0.1:8000";

chrome.runtime.onMessage.addListener(async (message) => {
  if (message.type !== "agent-run") return;

  const run = message.run;
  const storage = await chrome.storage.local.get(["runs"]);
  const runs = storage.runs || [];
  runs.push(run);
  await chrome.storage.local.set({ runs });

  await fetch(`${API_BASE}/agents/rank`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ runs, top_k: 20 })
  });
});
