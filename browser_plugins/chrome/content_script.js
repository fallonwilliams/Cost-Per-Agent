(function () {
  window.addEventListener("message", (event) => {
    if (event.source !== window) return;
    const payload = event.data;
    if (!payload || payload.type !== "RECURSIVE_AGENT_RUN") return;
    chrome.runtime.sendMessage({ type: "agent-run", run: payload.run });
  });
})();
