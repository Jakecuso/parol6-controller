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

function sendStop() {
  socket.emit("stop");
}

function sendHome() {
  socket.emit("home");
}
