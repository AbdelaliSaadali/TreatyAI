"""Store Groq credentials in macOS login Keychain without a plaintext file.

The local setup endpoint accepts a credential over loopback and never logs it.
Keychain is the storage boundary; this does not bypass macOS account security.
"""
from __future__ import annotations

import os
import platform
import re
import subprocess

from groq_provider import KEYCHAIN_SERVICE


class KeychainError(RuntimeError):
    pass


def store_groq_key(secret: str) -> None:
    if platform.system() != "Darwin":
        raise KeychainError("Keychain credential storage is available on macOS only.")
    if not re.fullmatch(r"gsk_[A-Za-z0-9]{30,120}", secret):
        raise KeychainError("Invalid Groq key format.")
    account = os.environ.get("USER", "")
    if not account:
        raise KeychainError("Unable to identify macOS account.")
    # The macOS security utility exposes the password briefly in its own argv,
    # but persists it only in Keychain. No secret is placed in Python source,
    # a shell command, the browser bundle, a repository or a plaintext file.
    try:
        result = subprocess.run(
            ["/usr/bin/security", "add-generic-password", "-a", account,
             "-s", KEYCHAIN_SERVICE, "-l", "TreatyAI Groq API", "-U",
             "-w", secret],
            capture_output=True, text=True, timeout=12, check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise KeychainError("macOS Keychain could not save the credential.") from exc
    if result.returncode:
        raise KeychainError("macOS Keychain refused the credential.")
