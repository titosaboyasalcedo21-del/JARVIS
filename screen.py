import asyncio
import base64
import json
import logging
import tempfile
import platform
from pathlib import Path

log = logging.getLogger("jarvis.screen")
IS_MAC = platform.system() == "Darwin"


async def get_active_windows() -> list[dict]:
    """Get list of visible windows."""
    if IS_MAC:
        script = """
set windowList to ""
tell application "System Events"
    set frontApp to name of first application process whose frontmost is true
    set visibleApps to every application process whose visible is true
    repeat with proc in visibleApps
        set appName to name of proc
        try
            set winCount to count of windows of proc
            if winCount > 0 then
                repeat with w in (windows of proc)
                    try
                        set winTitle to name of w
                        if winTitle is not "" and winTitle is not missing value then
                            set windowList to windowList & appName & "|||" & winTitle & "|||" & (appName = frontApp) & linefeed
                        end if
                    end try
                end repeat
            end if
        end try
    end repeat
end tell
return windowList
"""
        try:
            proc = await asyncio.create_subprocess_exec("osascript", "-e", script, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)
            if proc.returncode != 0: return []
            windows = []
            for line in stdout.decode().strip().split("\n"):
                parts = line.strip().split("|||")
                if len(parts) >= 3:
                    windows.append({"app": parts[0].strip(), "title": parts[1].strip(), "frontmost": parts[2].strip().lower() == "true"})
            return windows
        except: return []
    else:
        # Linux (Ubuntu) implementation using wmctrl
        try:
            proc = await asyncio.create_subprocess_exec("wmctrl", "-lG", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            if proc.returncode != 0: return []
            windows = []
            for line in stdout.decode().strip().split("\n"):
                parts = line.split(None, 6)
                if len(parts) >= 7:
                    title = parts[6]
                    app = title.split(" - ")[-1] if " - " in title else title
                    windows.append({"app": app, "title": title, "frontmost": False})
            return windows
        except: return []


async def get_running_apps() -> list[str]:
    """Get list of running application names (visible only)."""
    if IS_MAC:
        script = 'tell application "System Events" to return name of every application process whose visible is true'
        try:
            proc = await asyncio.create_subprocess_exec("osascript", "-e", script, stdout=asyncio.subprocess.PIPE)
            stdout, _ = await proc.communicate()
            if proc.returncode == 0: return [a.strip() for a in stdout.decode().strip().split(",") if a.strip()]
        except: pass
    else:
        # Linux: extract unique app names from window list
        wins = await get_active_windows()
        return list(set(w["app"] for w in wins))
    return []


async def take_screenshot(display_only: bool = True) -> str | None:
    """Take a screenshot and return base64 PNG."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        tmp_path = f.name

    try:
        if IS_MAC:
            cmd = ["screencapture", "-x"]
            if display_only: cmd.append("-m")
            cmd.append(tmp_path)
        else:
            # Linux: Requires 'scrot' (sudo apt install scrot)
            cmd = ["scrot", tmp_path]

        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await asyncio.wait_for(proc.communicate(), timeout=10)

        if proc.returncode != 0 or not Path(tmp_path).exists(): return None
        data = Path(tmp_path).read_bytes()
        return base64.b64encode(data).decode()
    except: return None
    finally:
        try: Path(tmp_path).unlink(missing_ok=True)
        except: pass


async def describe_screen(anthropic_client) -> str:
    """Describe what's on the user's screen."""
    screenshot_b64 = await take_screenshot()
    if screenshot_b64 and anthropic_client:
        try:
            response = await anthropic_client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=300,
                system="Eres JARVIS analizando una captura de pantalla. Describe de forma concisa qué aplicaciones y contenido ves. Máximo 2-4 frases. Responde en ESPAÑOL.",
                messages=[{"role": "user", "content": [{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": screenshot_b64}}, {"type": "text", "text": "¿Qué hay en mi pantalla?"}]}],
            )
            return response.content[0].text
        except: pass

    windows = await get_active_windows()
    if not windows: return "I wasn't able to see your screen, sir."

    context_parts = [f"{w['app']}: {w['title']}" for w in windows]
    if anthropic_client:
        try:
            response = await anthropic_client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=100,
                system="Eres JARVIS. Resume en qué está trabajando el usuario basándote en estas ventanas. Máximo 1-2 frases. Responde en ESPAÑOL.",
                messages=[{"role": "user", "content": "Ventanas abiertas:\n" + "\n".join(context_parts)}],
            )
            return response.content[0].text
        except: pass
    return f"You have {len(windows)} windows open, including {windows[0]['app']}."


def format_windows_for_context(windows: list[dict]) -> str:
    if not windows: return ""
    lines = ["Currently open on your desktop:"]
    for w in windows: lines.append(f"  - {w['app']}: {w['title']}")
    return "\n".join(lines)
