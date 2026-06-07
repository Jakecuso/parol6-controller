# Remote Access — control & develop the Pi from your computer

You never need a monitor or keyboard on the Pi. There are two separate channels,
and on a home network **neither needs any port-forwarding or firewall changes**.

| Channel | Address | What it's for |
|---|---|---|
| **Web UI** | `http://parol6.local:5050` | Driving the **robot** (any browser) |
| **SSH** | `ssh <user>@parol6.local` | Administering the **Pi** (terminal) |

The web UI is already exposed to your whole LAN by design — that's how you
control the arm from your phone or Mac. SSH is how you run commands, read logs,
and edit code.

---

## SSH (terminal access)

Enabled when you flash the card (Step 1 of [PI_SETUP.md](PI_SETUP.md)). From your
computer:

```bash
ssh pi@parol6.local          # use the username you set
```

Common things you'll do over SSH:
```bash
sudo systemctl status parol6     # is the controller running?
sudo systemctl restart parol6    # restart it
journalctl -u parol6 -f          # watch live logs
cd ~/parol6-controller && ./scripts/update.sh   # update to latest
```

### Passwordless login (optional, nicer)
Copy your SSH key so you don't type a password each time:
```bash
ssh-copy-id pi@parol6.local
```

---

## VS Code Remote-SSH (the comfortable dev setup)

This is the best way to edit and debug the Pi from your computer — the Pi's files
and a terminal open right inside VS Code on your big screen.

1. In VS Code, install the **Remote - SSH** extension.
2. Open the Command Palette (`Cmd/Ctrl+Shift+P`) → **Remote-SSH: Connect to Host…**
3. Enter `pi@parol6.local`, enter your password.
4. **File → Open Folder →** `/home/pi/parol6-controller`.

Now you edit files, run commands in the integrated terminal, and tail logs — all
from your machine, in one window. It feels like the Pi is local.

> 💡 **Tip — keep heavy tools OFF the Pi.** Run your editor / AI coding tools on
> your *computer* and connect to the Pi, rather than running them *on* the Pi. A
> small (2–4GB) Pi can run out of memory and lock up if it's doing robot work
> **and** hosting a heavy dev tool at the same time. Remote-SSH keeps the Pi
> light — it just serves files; the editor runs on your machine.

---

## Reaching the Pi from outside your home (optional)

Everything above assumes your computer and the Pi are on the **same network**.

If you want to reach the Pi from elsewhere (campus, a friend's house), **do NOT
port-forward it** — the controller has no login, so exposing it to the internet
would let anyone drive your arm. Instead use **[Tailscale](https://tailscale.com/)**:

```bash
# on the Pi, once:
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Install Tailscale on your laptop/phone too (same account) and you get a private,
encrypted connection to the Pi from anywhere — with **no open ports** and no
router config. Then use the Pi's Tailscale name/IP in place of `parol6.local`.

---

## Quick reference

```bash
# control the robot
open http://parol6.local:5050        # (just open it in a browser)

# admin the pi
ssh pi@parol6.local
sudo systemctl status parol6
journalctl -u parol6 -f
```
