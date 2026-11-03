"""Run the worker automatically with macOS launchd (the Mac's built-in scheduler)."""
import os
import subprocess
from pathlib import Path

from . import config

LABEL = "com.contentengine.worker"
PLIST = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def plist(minutes):
    py = config.ROOT / ".venv" / "bin" / "python"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>{LABEL}</string>
  <key>ProgramArguments</key>
  <array><string>{py}</string><string>-m</string><string>engine</string><string>run</string></array>
  <key>WorkingDirectory</key><string>{config.ROOT}</string>
  <key>StartInterval</key><integer>{minutes * 60}</integer>
  <key>RunAtLoad</key><true/>
  <key>ProcessType</key><string>Interactive</string>
  <key>StandardOutPath</key><string>{config.LOGS_DIR / 'launchd.log'}</string>
  <key>StandardErrorPath</key><string>{config.LOGS_DIR / 'launchd.log'}</string>
</dict>
</plist>
"""


def install(minutes=30):
    config.LOGS_DIR.mkdir(exist_ok=True)
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    if PLIST.exists():
        subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", str(PLIST)], capture_output=True)
    PLIST.write_text(plist(minutes))
    subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(PLIST)], check=True)
    print(f"Scheduled: the worker now runs every {minutes} minutes while you're logged in.\n"
          f"Log: {config.LOGS_DIR / 'worker.log'}\nTip: keep the Mac plugged in; renders are slow on battery.")


def uninstall():
    if PLIST.exists():
        subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", str(PLIST)], capture_output=True)
        PLIST.unlink()
        print("Schedule removed.")
    else:
        print("No schedule installed.")


def installed():
    return PLIST.exists()
