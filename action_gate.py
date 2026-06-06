import logging
import re

log = logging.getLogger("jarvis.action_gate")

SAFE_ACTIONS = {
    "remember",
    "add_task",
    "complete_task",
    "add_note",
    "create_note",
    "read_note",
    "screen",
    "browse",
    "research",
}

CONFIRM_ACTIONS = {"build", "prompt_project", "open_terminal", "run_python"}

DANGEROUS_ACTIONS = {"delete", "send_mail", "git_push", "deploy"}


def _target_is_dangerous(target: str) -> bool:
    if not target:
        return False
    t = target.lower()
    # Any explicit destructive / remote action keywords => confirmation required
    keywords = ["rm", "delete", "remove", "push", "send", "deploy"]
    return any(k in t for k in keywords)


def is_safe(action: str) -> bool:
    """Return True if the action is always safe to execute without confirmation."""
    return (action or "").lower() in SAFE_ACTIONS


def is_dangerous(action: str) -> bool:
    """Return True if the action is dangerous and must be blocked."""
    a = (action or "").lower()
    return a in DANGEROUS_ACTIONS


def needs_confirmation(action: str, target: str) -> bool:
    """Return True if the action requires user confirmation (based on action+target)."""
    a = (action or "").lower()
    if _target_is_dangerous(target):
        return True
    if a in CONFIRM_ACTIONS:
        return True
    # If it's dangerous, never allow; treat as confirmation requirement but will be blocked earlier.
    if a in DANGEROUS_ACTIONS:
        return True
    return False


def _contains_any(code: str, patterns: list[str]) -> bool:
    return any(re.search(p, code, flags=re.IGNORECASE | re.MULTILINE) for p in patterns)


def validate_python_code(code: str) -> tuple[bool, str]:
    """Validate python code before executing in python_sandbox.

    Returns: (is_safe, reason)
    """
    if not code or not isinstance(code, str):
        return False, "Empty code"

    # Hard blocks
    blocked_patterns = [
        r"\bos\.remove\b",
        r"\bshutil\.rmtree\b",
        r"\bsubprocess\b",
        r"open\([^\)]*,\s*['\"]w['\"]\s*\)",  # open(..., 'w')
        r"open\([^\)]*,\s*['\"]a['\"]\s*\)",  # open(..., 'a')
        r"\b__import__\b",
        r"\bexec\b\s*\(",
        r"\beval\b\s*\(",
    ]

    # Path-based checks: block writes outside /tmp (best-effort)
    # Common unsafe patterns: /etc/, /root/, home directories, or absolute paths.
    unsafe_path_patterns = [
        r"/etc/",
        r"/root/",
        r"/home/",
        r"/var/",
        r"/usr/",
        r"/opt/",
        r"/bin/",
        r"/sbin/",
        r"\.\./",
        r"/tmp/.*write",  # harmless-ish placeholder, but keep strict
    ]

    if _contains_any(code, blocked_patterns):
        return False, "Blocked code pattern (destructive/unsafe API)"

    # If code looks like it writes to absolute paths, block (conservative)
    if _contains_any(code, unsafe_path_patterns):
        return False, "Blocked code: potential file-system access outside /tmp"

    # If code tries to run system commands via os.system or popen (extra conservative)
    extra_blocked_patterns = [
        r"\bos\.system\b",
        r"\bos\.popen\b",
        r"\bpopen\b\s*\(",
    ]
    if _contains_any(code, extra_blocked_patterns):
        return False, "Blocked code pattern (system execution)"

    return True, "OK"

