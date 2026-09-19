"""
tests/test_send_message_verification.py
Tests for verified messaging, error modal detection, contact resolution, and anti-hallucination guards.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from actions.send_message import (
    _check_telegram_error_dialog,
    _verify_chat_opened,
    send_message,
)


def test_verify_chat_opened_detects_stuck_search():
    """If clipboard contains the exact contact name, focus is still in search box."""
    with patch("actions.send_message.pyperclip.paste", return_value="ritik"):
        with patch("actions.send_message.pyautogui.hotkey"):
            assert _verify_chat_opened("ritik") is False


def test_verify_chat_opened_detects_success():
    """If clipboard does not match contact name, chat opened successfully."""
    with patch("actions.send_message.pyperclip.paste", return_value=""):
        with patch("actions.send_message.pyautogui.hotkey"):
            assert _verify_chat_opened("ritik") is True


def test_check_telegram_error_dialog_detects_popup():
    """Detects modal popup when clipboard or window title indicates not found."""
    with patch("actions.send_message.pyperclip.paste", return_value="Username @ritik not found."):
        with patch("actions.send_message.pyautogui.hotkey"):
            assert _check_telegram_error_dialog() is True


def test_send_message_requires_parameters():
    """Rejects empty recipient or message."""
    res1 = send_message({"platform": "telegram", "receiver": "", "message_text": "hello"})
    assert "specify a recipient" in res1.lower()

    res2 = send_message({"platform": "telegram", "receiver": "ritik", "message_text": ""})
    assert "specify the message content" in res2.lower()


def test_telegram_plain_name_uses_desktop_search_not_domain():
    """A plain contact name (like 'ritik') MUST NOT call tg://resolve?domain=ritik."""
    with patch("actions.send_message._send_telegram_desktop_contact", return_value="Searched in Telegram Desktop") as mock_desk:
        with patch("os.system") as mock_os:
            res = send_message({"platform": "telegram", "receiver": "ritik", "message_text": "hii"})
            assert "Searched in Telegram Desktop" in res
            # Ensure start tg://resolve was NOT called for plain name
            mock_os.assert_not_called()
            mock_desk.assert_called_once_with("ritik", "hii")


def test_telegram_explicit_username_uses_domain():
    """An explicit @username (like '@ritik') uses tg://resolve?domain=ritik and checks for popup error."""
    with patch("os.system") as mock_os:
        with patch("actions.send_message._check_telegram_error_dialog", return_value=True):
            with patch("actions.send_message.pyautogui.press") as mock_press:
                res = send_message({"platform": "telegram", "receiver": "@ritik", "message_text": "hii"})
                mock_os.assert_called_once()
                assert "not found" in res.lower() or "nahi mila" in res.lower()
                mock_press.assert_called_with("escape")


def test_contacts_resolution_username_for_telegram():
    """Contacts book resolves username for telegram when available."""
    mock_contact = {"phone": "9876543210", "username": "ritik_real", "platform": "telegram"}
    with patch("memory.contacts.resolve_contact", return_value=mock_contact):
        with patch("actions.send_message._send_telegram_desktop_contact", return_value="sent") as mock_desk:
            res = send_message({"platform": "telegram", "receiver": "ritik", "message_text": "hii"})
            assert res == "sent"
            mock_desk.assert_called_once_with("ritik_real", "hii")
