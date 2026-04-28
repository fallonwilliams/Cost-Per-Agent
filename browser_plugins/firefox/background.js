const API_BASE = "http://127.0.0.1:8000";

browser.runtime.onMessage.addListener(async (message) => {
  if (message.type !== "agent-run") return;

  const storage = await browser.storage.local.get("runs");
  const runs = storage.runs || [];
  runs.push(message.run);
  await browser.storage.local.set({ runs });

  await fetch(`${API_BASE}/agents/rank`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ runs, top_k: 20 })
  });
});
