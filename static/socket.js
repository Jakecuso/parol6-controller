const socket = io();

window.poseState = {
  joints: [0, 0, 0, 0, 0, 0],
  xyz:    [0, 0, 0, 0, 0, 0],
  status: "unknown",
  error:  false,
};

socket.on("pose_update", (data) => {
  Object.assign(window.poseState, data);
  document.dispatchEvent(new CustomEvent("pose_update", { detail: data }));
  const pill = document.getElementById("estop-pill");
  if (pill) pill.style.display = data.estop ? "flex" : "none";
});

socket.on("connect", () => {
  const pill = document.getElementById("status-pill");
  if (pill) pill.innerHTML = '<span class="dot dot-green"></span> Connected';
});

socket.on("disconnect", () => {
  const pill = document.getElementById("status-pill");
  if (pill) pill.innerHTML = '<span class="dot dot-red"></span> Disconnected';
});

socket.on("connect_error", (err) => {
  const pill = document.getElementById("status-pill");
  if (pill) pill.innerHTML = '<span class="dot dot-red"></span> Error';
  console.error("[socket] connect error:", err.message);
});

socket.on("robot:error", (data) => {
  let toast = document.getElementById("robot-err-toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "robot-err-toast";
    toast.style.cssText = [
      "position:fixed", "bottom:28px", "left:50%", "transform:translateX(-50%)",
      "background:#c62828", "color:#fff", "padding:10px 20px",
      "border-radius:14px", "font-size:13px", "font-weight:600",
      "z-index:9999", "box-shadow:0 4px 20px rgba(0,0,0,.5)",
      "pointer-events:none", "display:none"
    ].join(";");
    document.body.appendChild(toast);
  }
  toast.textContent = data.msg;
  toast.style.display = "block";
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { toast.style.display = "none"; }, 4000);
});

function sendStop() {
  socket.emit("stop");
}

function sendHome() {
  socket.emit("home");
}
