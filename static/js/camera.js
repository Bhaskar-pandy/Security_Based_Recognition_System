// Small helpers shared by the Face Access page and the Register Face page.

const FRAME_W = 480, FRAME_H = 360;   // size of the picture sent to the server

async function startCamera(video) {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    throw new Error("Camera is not available. Open the site at http://127.0.0.1:5000 or over HTTPS.");
  }
  const stream = await navigator.mediaDevices.getUserMedia(
    { video: { width: 640, height: 480, facingMode: "user" }, audio: false });
  video.srcObject = stream;
  await video.play();
  return stream;
}

function stopCamera(stream, video) {
  if (stream) stream.getTracks().forEach(t => t.stop());
  video.srcObject = null;
}

// Take one picture from the video and return it as a JPEG "data URL".
function grabFrame(video) {
  const canvas = document.createElement("canvas");
  canvas.width = FRAME_W; canvas.height = FRAME_H;
  canvas.getContext("2d").drawImage(video, 0, 0, FRAME_W, FRAME_H);
  return canvas.toDataURL("image/jpeg", 0.7);
}

// Draw the face rectangle. box = {x, y, w, h} as fractions (0..1), or null to clear.
function drawBox(overlay, box, color) {
  overlay.width = overlay.clientWidth; overlay.height = overlay.clientHeight;
  const ctx = overlay.getContext("2d");
  ctx.clearRect(0, 0, overlay.width, overlay.height);
  if (!box) return;
  ctx.strokeStyle = color || "#ff7a00"; ctx.lineWidth = 3;
  ctx.strokeRect(box.x * overlay.width, box.y * overlay.height, box.w * overlay.width, box.h * overlay.height);
}

// Send JSON to the server (with the CSRF token that protects against forged requests).
async function postJSON(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json",
               "X-CSRF-Token": document.querySelector('meta[name="csrf"]').content },
    body: JSON.stringify(body || {}),
  });
  const data = await response.json().catch(() => ({ state: "error", message: "Server error (" + response.status + ")" }));
  return data;
}

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

// Run a full face check (random challenges, optional hand step) against the server.
// purpose: "door" (kiosk) or "login" (website sign-in). onUpdate(text, kind, result) is called on every
// step; kind = "info" | "granted" | "denied" | "hand". Resolves with the final result object.
async function runAccessCheck(video, overlay, purpose, onUpdate, nextUrl) {
  let stream = null;
  try {
    onUpdate("Starting camera…", "info");
    stream = await startCamera(video);
    const start = await postJSON("/api/access/start", { purpose });
    if (!start.attempt) { onUpdate(start.message || "Could not start.", "denied"); return { state: "error" }; }
    onUpdate("Look straight at the camera", "info");
    while (true) {
      const r = await postJSON("/api/access/frame", { attempt: start.attempt, image: grabFrame(video), next: nextUrl || "" });
      if (r.state === "granted") { drawBox(overlay, null); onUpdate(r.message, "granted", r); return r; }
      if (r.state === "denied" || r.state === "error") { drawBox(overlay, null); onUpdate(r.message, "denied", r); return r; }
      drawBox(overlay, r.box, r.step === "hand" ? "#3b5bdb" : undefined);
      onUpdate(r.message, r.step === "hand" ? "hand" : "info", r);
      await sleep(40);
    }
  } catch (e) {
    onUpdate(e.message, "denied");
    return { state: "error" };
  } finally {
    stopCamera(stream, video);
  }
}
