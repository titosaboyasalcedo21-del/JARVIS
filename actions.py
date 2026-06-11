import asyncio
import logging
import os
import re
import sys
import time
import platform
from pathlib import Path
from urllib.parse import quote

log = logging.getLogger("jarvis.actions")

def _safe_shell(arg: str) -> str:
    """Escape a shell argument using shlex.quote()."""
    import shlex
    return shlex.quote(arg)

def _safe_applescript(value: str) -> str:
    """Escape a value for AppleScript (quote escaping)."""
    # AppleScript uses " for strings, escape any internal "
    return value.replace('"', '\"')

DESKTOP_PATH = Path.home() / "Desktop"
IS_MAC = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"


async def _mark_terminal_as_jarvis(revert_after: float = 5.0):
    """Shows the user JARVIS is active in that terminal."""
    if not IS_MAC:
        # On Linux, we could try to change terminal colors via ANSI codes,
        # but for now we'll just log it.
        return

    # macOS implementation
    script_save = (
        'tell application "Terminal"\n'
        '    return name of current settings of front window\n'
        'end tell'
    )
    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script_save,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        original_profile = stdout.decode().strip()

        # Switch to Ocean
        script_set = (
            'tell application "Terminal"\n'
            '    set current settings of front window to settings set "Ocean"\n'
            'end tell'
        )
        proc2 = await asyncio.create_subprocess_exec(
            "osascript", "-e", script_set,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc2.communicate()

        # Schedule revert
        if original_profile and original_profile != "Ocean":
            async def _revert_later():
                await asyncio.sleep(revert_after)
                await _revert_terminal_theme(original_profile)

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(_revert_later())
            except RuntimeError:
                # Fallback when called without a running loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.create_task(_revert_later())
                loop.run_until_complete(asyncio.sleep(revert_after + 0.1))
                loop.close()
    except Exception:
        pass


async def _revert_terminal_theme(profile_name: str):
    """Revert a Terminal window back to its original profile (macOS only)."""
    if not IS_MAC:
        return
    escaped = profile_name.replace('"', '\\"')
    script = (
        'tell application "Terminal"\n'
        f'    set current settings of front window to settings set "{escaped}"\n'
        'end tell'
    )
    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
    except Exception:
        pass


async def open_terminal(command: str = "") -> dict:
    """Open a terminal and optionally run a command."""
    if IS_MAC:
        if command:
            escaped = command.replace('"', '\\"')
            script = (
                'tell application "Terminal"\n'
                "    activate\n"
                f'    do script "{escaped}"\n'
                "end tell"
            )
        else:
            script = (
                'tell application "Terminal"\n'
                "    activate\n"
                "end tell"
            )
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    else:
        # Linux (Ubuntu) implementation
        if command:
            # We use gnome-terminal which is standard on Ubuntu
            # 'bash -c' allows running a command and then keeping the terminal open with 'exec bash'
            full_cmd = f'gnome-terminal -- bash -c {_safe_shell(command) + "; exec bash"}'
        else:
            full_cmd = 'gnome-terminal'
        
        proc = await asyncio.create_subprocess_exec(
            "bash", "-c", full_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    _, stderr = await proc.communicate()
    success = proc.returncode == 0
    if not success:
        log.error(f"open_terminal failed: {stderr.decode()}")
    elif IS_MAC:
        await _mark_terminal_as_jarvis()
        
    return {
        "success": success,
        "confirmation": "Terminal is open, sir." if success else "I had trouble opening Terminal, sir.",
    }


async def open_browser(url: str, browser: str = "chrome") -> dict:
    """Open URL in user's browser."""
    if IS_MAC:
        escaped_url = url.replace('"', '\\"')
        if browser.lower() == "firefox":
            app_name = "Firefox"
            script = f'tell application "Firefox" to open location "{escaped_url}"'
        else:
            app_name = "Google Chrome"
            script = f'tell application "Google Chrome" to open location "{escaped_url}"'
        
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        app_display = app_name
    else:
        # Linux (Ubuntu) implementation
        # xdg-open is the universal way to open URLs in Linux
        proc = await asyncio.create_subprocess_exec(
            "xdg-open", url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        app_display = "the browser"

    _, stderr = await proc.communicate()
    success = proc.returncode == 0
    if not success:
        log.error(f"open_browser failed: {stderr.decode()}")
        
    return {
        "success": success,
        "confirmation": f"Pulled that up in {app_display}, sir." if success else "I ran into a problem opening the browser, sir.",
    }


async def open_chrome(url: str) -> dict:
    return await open_browser(url, "chrome")


async def open_overlay() -> dict:
    """Open the Linux JARVIS overlay window for the orb display."""
    overlay_script = Path(__file__).parent / "desktop-overlay" / "linux_overlay.py"
    if not overlay_script.exists():
        return {
            "success": False,
            "confirmation": "Overlay script not found, sir.",
        }

    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        str(overlay_script),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # Do not wait for the overlay app to exit.
    # If the process fails immediately, capture the error for debugging.
    await asyncio.sleep(0.1)
    success = proc.returncode in (0, None)
    if proc.returncode is None:
        return {
            "success": True,
            "confirmation": "JARVIS overlay should appear shortly, sir.",
        }
    if not success:
        stderr = (await proc.stderr.read()).decode('utf-8', errors='ignore') if proc.stderr else ""
        log.error(f"open_overlay failed: {stderr}")
        return {
            "success": False,
            "confirmation": "I could not launch the overlay, sir.",
        }

    return {
        "success": True,
        "confirmation": "JARVIS overlay should appear shortly, sir.",
    }


async def open_claude_in_project(project_dir: str, prompt: str) -> dict:
    """Open Terminal, cd to project dir, run Claude Code interactively."""
    claude_md = Path(project_dir) / "CLAUDE.md"
    claude_md.write_text(f"# Task\n\n{prompt}\n\nBuild this completely. If web app, make index.html work standalone.\n")

    if IS_MAC:
        script = (
            'tell application "Terminal"\n'
            "    activate\n"
            f'    do script "cd {project_dir} && claude --dangerously-skip-permissions"\n'
            "end tell"
        )
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    else:
        # Linux implementation
        cmd = f'cd {project_dir} && claude --dangerously-skip-permissions'
        full_cmd = f'gnome-terminal -- bash -c "{cmd}; exec bash"'
        proc = await asyncio.create_subprocess_exec(
            "bash", "-c", full_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    _, stderr = await proc.communicate()
    success = proc.returncode == 0
    if not success:
        log.error(f"open_claude_in_project failed: {stderr.decode()}")
    elif IS_MAC:
        await _mark_terminal_as_jarvis()
        
    return {
        "success": success,
        "confirmation": "Claude Code is running in Terminal, sir. You can watch the progress."
        if success
        else "Had trouble spawning Claude Code, sir.",
    }


async def prompt_existing_terminal(project_name: str, prompt: str) -> dict:
    """Find a Terminal window matching a project name and type a prompt into it."""
    if IS_MAC:
        escaped_name = project_name.replace('"', '\\"')
        escaped_prompt = prompt.replace("\\", "\\\\").replace('"', '\\"')
        script = f'''
tell application "Terminal"
    set matched to false
    set targetWindow to missing value
    repeat with w in windows
        if name of w contains "{escaped_name}" then
            set targetWindow to w
            set matched to true
            exit repeat
        end if
    end repeat
    if not matched then return "NOT_FOUND"
    set index of targetWindow to 1
    activate
end tell
delay 1
tell application "System Events"
    tell process "Terminal"
        set frontmost to true
        delay 0.3
        keystroke "{escaped_prompt}"
        keystroke return
    end tell
end tell
return "OK"
'''
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    else:
        # Linux (Ubuntu) implementation using xdotool
        # Requires: sudo apt install xdotool
        escaped_prompt = prompt.replace('"', '\\"')
        # Try to find window by name, focus it, and type
        script = f'''
WID=$(xdotool search --name "{project_name}" | head -n 1)
if [ -z "$WID" ]; then
    echo "NOT_FOUND"
else
    xdotool windowactivate $WID
    sleep 0.5
    xdotool type "{escaped_prompt}"
    xdotool key Return
    echo "OK"
fi
'''
        proc = await asyncio.create_subprocess_exec(
            "bash", "-c", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
    result = stdout.decode().strip()
    
    if "NOT_FOUND" in result:
        return {"success": False, "confirmation": f"Couldn't find a terminal for {project_name}, sir."}

    success = proc.returncode == 0
    if success and IS_MAC:
        await _mark_terminal_as_jarvis()

    return {
        "success": success,
        "confirmation": f"Sent that to {project_name}, sir." if success else "Had trouble reaching that terminal, sir.",
    }


async def get_chrome_tab_info() -> dict:
    """Read current Chrome tab info (macOS only for now)."""
    if not IS_MAC:
        return {} # Linux browser automation via xdotool is unreliable
        
    script = (
        'tell application "Google Chrome"\n'
        "    set tabTitle to title of active tab of front window\n"
        "    set tabURL to URL of active tab of front window\n"
        '    return tabTitle & "|" & tabURL\n'
        "end tell"
    )
    try:
        proc = await asyncio.create_subprocess_exec("osascript", "-e", script, stdout=asyncio.subprocess.PIPE)
        stdout, _ = await proc.communicate()
        if proc.returncode == 0:
            result = stdout.decode().strip()
            parts = result.split("|", 1)
            if len(parts) == 2: return {"title": parts[0], "url": parts[1]}
    except:
        pass
    return {}


async def monitor_build(project_dir: str, ws=None, synthesize_fn=None) -> None:
    """Monitor a Claude Code build for completion."""
    import base64
    output_file = Path(project_dir) / ".jarvis_output.txt"
    start = time.time()
    timeout = 600

    while time.time() - start < timeout:
        await asyncio.sleep(5)
        if output_file.exists():
            content = output_file.read_text()
            if "--- JARVIS TASK COMPLETE ---" in content:
                if ws and synthesize_fn:
                    try:
                        msg = "The build is complete, sir."
                        audio_bytes, fmt = await synthesize_fn(msg)
                        if audio_bytes:
                            await ws.send_json({"type": "status", "state": "speaking"})
                            audio_msg = _build_audio_message(audio_bytes, fmt, msg)
                            if audio_msg:
                                await ws.send_json(audio_msg)
                            await ws.send_json({"type": "status", "state": "idle"})
                    except:
                        pass
                return
    log.warning(f"Build timed out in {project_dir}")


async def execute_action(intent: dict, projects: list = None) -> dict:
    """Route intent to action."""
    action = intent.get("action", "chat")
    target = intent.get("target", "")

    if action == "open_terminal":
        return await open_terminal("claude --dangerously-skip-permissions")
    elif action == "browse":
        url = target if target.startswith("http") else f"https://www.google.com/search?q={quote(target)}"
        return await open_browser(url)
    elif action == "build":
        project_name = _generate_project_name(target)
        project_dir = str(DESKTOP_PATH / project_name)
        os.makedirs(project_dir, exist_ok=True)
        result = await open_claude_in_project(project_dir, target)
        result["project_dir"] = project_dir
        return result
    return {"success": False, "confirmation": "", "project_dir": None}


def _generate_project_name(prompt: str) -> str:
    """Generate kebab-case project name."""
    quoted = re.search(r'"([^"]+)"', prompt)
    if quoted:
        name = re.sub(r"[^a-zA-Z0-9\s-]", "", quoted.group(1)).strip()
        if name: return re.sub(r"[\s]+", "-", name.lower())
    
    words = re.sub(r"[^a-zA-Z0-9\s]", "", prompt.lower()).split()
    skip = {"a", "the", "an", "me", "build", "create", "make", "for", "with", "and", "to", "of", "i", "want", "need", "new"}
    meaningful = [w for w in words if w not in skip and len(w) > 2][:4]
    return "-".join(meaningful) if meaningful else "jarvis-project"
