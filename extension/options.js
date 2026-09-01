const bg = (m) => new Promise((r) => chrome.runtime.sendMessage(m, r));
(async () => {
  const c = await bg({ type: "getConfig" });
  document.getElementById("api").value = c.api || "http://127.0.0.1:8770";
  document.getElementById("secret").value = c.secret || "";
})();
document.getElementById("save").onclick = async () => {
  await bg({ type: "setConfig",
    apiBase: document.getElementById("api").value.trim() || "http://127.0.0.1:8770",
    secret: document.getElementById("secret").value.trim() });
  document.getElementById("status").textContent = "saved.";
};
