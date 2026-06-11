import asyncio
import logging
import platform
import os
import re
from pathlib import Path
from datetime import datetime

log = logging.getLogger("jarvis.notes")
IS_MAC = platform.system() == "Darwin"
NOTES_DIR = Path.home() / "Documents" / "JarvisNotes"

if not IS_MAC:
    NOTES_DIR.mkdir(parents=True, exist_ok=True)


async def _run_notes_script(script: str, timeout: float = 10) -> str:
    """Run an AppleScript against Notes.app (macOS only)."""
    if not IS_MAC: return ""
    try:
        proc = await asyncio.create_subprocess_exec("osascript", "-e", script, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        if proc.returncode != 0: return ""
        return stdout.decode().strip()
    except (asyncio.TimeoutError, FileNotFoundError, OSError) as e:
        log.debug("Notes script failed: %s", e)
        return ""


async def get_recent_notes(count: int = 10) -> list[dict]:
    """Get most recent notes."""
    if IS_MAC:
        script = f'''
tell application "Notes"
    set output to ""
    set allNotes to every note
    set limit to count of allNotes
    if limit > {count} then set limit to {count}
    repeat with i from 1 to limit
        set n to item i of allNotes
        set output to output & name of n & "|||" & (creation date of n as string) & "|||" & (name of container of n) & linefeed
    end repeat
    return output
end tell
'''
        raw = await _run_notes_script(script, timeout=15)
        if not raw: return []
        notes = []
        for line in raw.split("\n"):
            parts = line.strip().split("|||")
            if len(parts) >= 3:
                notes.append({"title": parts[0].strip(), "date": parts[1].strip(), "folder": parts[2].strip()})
        return notes
    else:
        # Linux: List files in JarvisNotes
        notes = []
        try:
            files = sorted(NOTES_DIR.glob("*.md"), key=os.path.getmtime, reverse=True)[:count]
            for f in files:
                mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
                notes.append({"title": f.stem, "date": mtime, "folder": "Local"})
        except (OSError, PermissionError) as e:
            log.debug("Notes file listing failed: %s", e)
        return notes


async def read_note(title_match: str) -> dict | None:
    """Read a note by title."""
    if IS_MAC:
        escaped = title_match.replace('"', '\\"')
        script = f'''
tell application "Notes"
    repeat with n in every note
        if name of n contains "{escaped}" then return (name of n) & "|||" & (plaintext of n)
    end repeat
    return ""
end tell
'''
        raw = await _run_notes_script(script)
        if not raw or "|||" not in raw: return None
        title, _, body = raw.partition("|||")
        return {"title": title.strip(), "body": body.strip()}
    else:
        # Linux: Read file
        try:
            for f in NOTES_DIR.glob("*.md"):
                if title_match.lower() in f.stem.lower():
                    return {"title": f.stem, "body": f.read_text()}
        except (OSError, PermissionError) as e:
            log.debug("Note read failed: %s", e)
        return None


async def search_notes_apple(query: str, count: int = 5) -> list[dict]:
    """Search notes by title keyword."""
    if IS_MAC:
        escaped = query.replace('"', '\\"')
        script = f'''
tell application "Notes"
    set output to ""
    set foundCount to 0
    repeat with n in every note
        if foundCount >= {count} then exit repeat
        if name of n contains "{escaped}" then
            set output to output & (name of n) & "|||" & (creation date of n as string) & linefeed
            set foundCount to foundCount + 1
        end if
    end repeat
    return output
end tell
'''
        raw = await _run_notes_script(script)
        if not raw: return []
        notes = []
        for line in raw.split("\n"):
            parts = line.strip().split("|||")
            if len(parts) >= 2: notes.append({"title": parts[0].strip(), "date": parts[1].strip()})
        return notes
    else:
        # Linux: search file names
        notes = []
        try:
            for f in NOTES_DIR.glob("*.md"):
                if query.lower() in f.stem.lower():
                    mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
                    notes.append({"title": f.stem, "date": mtime})
                    if len(notes) >= count: break
        except (OSError, PermissionError) as e:
            log.debug("Notes search failed: %s", e)
        return notes


async def create_local_note(title: str, body: str, folder: str = "Notes") -> bool:
    """Create a new local markdown note."""
    if IS_MAC:
        html_body = _body_to_html(body)
        escaped_title, escaped_body, escaped_folder = title.replace('"', '\\"'), html_body.replace('"', '\\"'), folder.replace('"', '\\"')
        script = f'tell application "Notes" to tell folder "{escaped_folder}" to make new note with properties {{name:"{escaped_title}", body:"{escaped_body}"}}'
        return (await _run_notes_script(script)) != ""
    else:
        # Linux: Save as .md file
        try:
            safe_title = re.sub(r'[^a-zA-Z0-9_\- ]', '', title).strip()
            filepath = NOTES_DIR / f"{safe_title}.md"
            filepath.write_text(body)
            log.info(f"Created local note: {filepath}")
            return True
        except (OSError, PermissionError) as e:
            log.warning(f"Note creation failed: {e}")
            return False


def _body_to_html(body: str) -> str:
    """Convert markdown-style checklists to HTML (macOS only)."""
    lines = body.split("\n")
    html_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped: html_lines.append("<br>")
        elif re.match(r"^-\s*\[x\]\s*", stripped, re.IGNORECASE):
            text = re.sub(r"^-\s*\[x\]\s*", "", stripped, flags=re.IGNORECASE)
            html_lines.append(f'<div><input type="checkbox" checked="checked"> {text}</div>')
        elif re.match(r"^-\s*\[\s?\]\s*", stripped):
            text = re.sub(r"^-\s*\[\s?\]\s*", "", stripped)
            html_lines.append(f'<div><input type="checkbox"> {text}</div>')
        elif re.match(r"^[-*+]\s+", stripped):
            text = re.sub(r"^[-*+]\s+", "", stripped)
            html_lines.append(f"<div>• {text}</div>")
        else: html_lines.append(f"<div>{stripped}</div>")
    return "\n".join(html_lines)


async def get_note_folders() -> list[str]:
    """Get list of note folder names."""
    if IS_MAC:
        script = 'tell application "Notes" to return name of every folder'
        raw = await _run_notes_script(script)
        return [f.strip() for f in raw.split(",") if f.strip()]
    return ["Local"]
