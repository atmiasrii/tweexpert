async function load() {
  const s = await chrome.runtime.sendMessage({ type: "safeguard" });
  const el = document.getElementById("meter");
  if (s.error) { el.textContent = "backend unreachable — set secret in Options"; return; }
  el.innerHTML = `
    <div class="row"><span>auto replies</span><b>${s.replies_auto}</b></div>
    <div class="row"><span>assisted replies</span><b>${s.replies_assisted}</b></div>
    <div class="row"><span>quiet now</span><b>${s.quiet_now ? "yes" : "no"}</b></div>
    <div class="row"><span>kill switch</span><b>${s.kill_switch ? "ON" : "off"}</b></div>`;
  document.getElementById("killbtn").onclick = async () => {
    await chrome.runtime.sendMessage({ type: "kill", on: !s.kill_switch });
    load();
  };
}
load();
