#!/usr/bin/env python3
# rev: 4 — send|fetch subcommands; shared MAIL_FLOW_LAB_TOKEN from Ansible
"""Lab mail test on mail_ip: `send` (SMTP 587 AUTH) or `fetch` (IMAP 993).

Usage:
  python3 mail_flow_lab_test.py send
  python3 mail_flow_lab_test.py fetch

Environment (both steps):
  MAIL_USER, MAIL_PASSWORD, TLS_SERVER_NAME, MAIL_FLOW_LAB_TOKEN
  MAIL_FLOW_LAB_TLS_INSECURE — 1/true = skip cert verify (lab)
send also needs: SMTP_HOST
fetch also needs: IMAP_HOST
"""
from __future__ import annotations

import email.message
import imaplib
import ipaddress
import os
import smtplib
import ssl
import sys

_tls_insecure_warned = False


def _env_tls_insecure() -> bool:
    v = os.environ.get("MAIL_FLOW_LAB_TLS_INSECURE", "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _ssl_context(peer_host: str) -> ssl.SSLContext:
    global _tls_insecure_warned
    if _env_tls_insecure():
        if not _tls_insecure_warned:
            print(
                "WARNING: MAIL_FLOW_LAB_TLS_INSECURE set — TLS certificate verification disabled (lab only).",
                file=sys.stderr,
            )
            _tls_insecure_warned = True
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    ctx = ssl.create_default_context()
    try:
        ipaddress.ip_address(peer_host)
    except ValueError:
        return ctx
    ctx.check_hostname = False
    return ctx


def _smtp_starttls(smtp: smtplib.SMTP, ctx: ssl.SSLContext, tls_name: str) -> None:
    try:
        smtp.starttls(context=ctx, server_hostname=tls_name)
    except TypeError:
        smtp.starttls(context=ctx)


def cmd_send() -> int:
    user = os.environ["MAIL_USER"]
    password = os.environ["MAIL_PASSWORD"]
    smtp_host = os.environ["SMTP_HOST"]
    tls_name = os.environ.get("TLS_SERVER_NAME", "mail.hell.sk")
    token = os.environ["MAIL_FLOW_LAB_TOKEN"]

    msg = email.message.EmailMessage()
    msg["Subject"] = f"[mail-flow-lab] {token}"
    msg["From"] = user
    msg["To"] = user
    msg["X-Mail-Flow-Lab"] = token
    msg.set_content(f"mail-flow-lab token={token}\n")

    ctx = _ssl_context(smtp_host)
    try:
        with smtplib.SMTP(smtp_host, 587, timeout=90) as s:
            s.ehlo()
            _smtp_starttls(s, ctx, tls_name)
            s.ehlo()
            s.login(user, password)
            s.send_message(msg)
    except Exception as e:
        print(f"SMTP failed: {e}", file=sys.stderr)
        return 1
    print(f"OK: SMTP sent (token {token})")
    return 0


def cmd_fetch() -> int:
    user = os.environ["MAIL_USER"]
    password = os.environ["MAIL_PASSWORD"]
    imap_host = os.environ["IMAP_HOST"]
    token = os.environ["MAIL_FLOW_LAB_TOKEN"]

    ctx = _ssl_context(imap_host)
    try:
        m = imaplib.IMAP4_SSL(imap_host, 993, ssl_context=ctx)
        m.login(user, password)
        m.select("INBOX", readonly=True)
        typ, data = m.search(None, "HEADER", "X-Mail-Flow-Lab", token)
        if typ != "OK":
            print(f"IMAP SEARCH failed: {typ} {data}", file=sys.stderr)
            return 1
        ids = data[0].split()
        if not ids:
            print(
                f"No message with X-Mail-Flow-Lab: {token}. Wait longer after send or check delivery.",
                file=sys.stderr,
            )
            return 1
        typ, msgdata = m.fetch(ids[-1], "(RFC822)")
        if typ != "OK" or not msgdata or msgdata[0] is None:
            print("IMAP FETCH failed", file=sys.stderr)
            return 1
        raw = msgdata[0][1]
        if not isinstance(raw, (bytes, bytearray)):
            print("Unexpected FETCH payload", file=sys.stderr)
            return 1
        text = raw.decode("utf-8", errors="replace")
        if token not in text:
            print("Fetched message missing expected token", file=sys.stderr)
            return 1
        m.logout()
    except Exception as e:
        print(f"IMAP failed: {e}", file=sys.stderr)
        return 1
    print(f"OK: IMAP fetch verified (token {token})")
    return 0


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ("send", "fetch"):
        print("Usage: mail_flow_lab_test.py send|fetch", file=sys.stderr)
        return 2
    if "MAIL_FLOW_LAB_TOKEN" not in os.environ or not os.environ["MAIL_FLOW_LAB_TOKEN"].strip():
        print("MAIL_FLOW_LAB_TOKEN must be set", file=sys.stderr)
        return 2
    if sys.argv[1] == "send":
        return cmd_send()
    return cmd_fetch()


if __name__ == "__main__":
    raise SystemExit(main())
