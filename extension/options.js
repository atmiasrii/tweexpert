(async () => {
  const { sharedSecret } = await chrome.storage.local.get("sharedSecret");
  if (sharedSecret) document.getElementById("secret").value = sharedSecret;
})();
document.getElementById("save").onclick = async () => {
  const secret = document.getElementById("secret").value.trim();
  await chrome.runtime.sendMessage({ type: "setSecret", secret });
  document.getElementById("status").textContent = "saved.";
};
