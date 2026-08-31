#!/usr/bin/env bash
# Browser service (§6, A-04). In fixture mode it just runs the browser process
# (no Xvfb needed). In playwright mode it starts Xvfb + a loopback noVNC surface
# for first-run/re-login (E-02, X-03), then runs the process headed under Xvfb.
set -e

ENGINE="${QUILL_BROWSER_ENGINE:-fixture}"

if [ "$ENGINE" = "playwright" ]; then
  echo "[browser] starting Xvfb + noVNC (loopback re-login surface)"
  Xvfb :99 -screen 0 1280x900x24 >/tmp/xvfb.log 2>&1 &
  sleep 1
  x11vnc -display :99 -nopw -localhost -forever -shared >/tmp/x11vnc.log 2>&1 &
  websockify --web /usr/share/novnc 6080 localhost:5900 >/tmp/novnc.log 2>&1 &
  echo "[browser] noVNC on http://127.0.0.1:6080/vnc.html (reach via tunnel only)"
fi

exec python -m quill.browser_proc
