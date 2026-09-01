const bg = (m) => new Promise((r) => chrome.runtime.sendMessage(m, r));
async function load() {
  const s = await bg({ type: "safeguard" });
  const el = document.getElementById("meter");
  if (!s || s.error) { el.textContent = "backend unreachable — open Options"; return; }
  el.innerHTML = `
    <div class="row"><span>auto replies</span><b>${s.replies_auto ?? 0}</b></div>
    <div class="row"><span>for-you replies</span><b>${s.replies_foryou ?? 0}</b></div>
    <div class="row"><span>quiet now</span><b>${s.quiet_now ? "yes" : "no"}</b></div>
    <div class="row"><span>kill switch</span><b>${s.kill_switch ? "ON" : "off"}</b></div>`;
  document.getElementById("killbtn").onclick = async () => {
    await bg({ type: "kill", on: !s.kill_switch }); load();
  };
}
document.getElementById("opts").onclick = (e) => { e.preventDefault(); chrome.runtime.openOptionsPage(); };
load();
