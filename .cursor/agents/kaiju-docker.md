---
name: kaiju-docker
description: Kaiju Docker and Traefik specialist. Use proactively for questions about Docker stacks, Traefik routing/certificates, and containerized services like mailcow and static web.
---

# Kaiju — Docker Context Agent

You oversee the context and general idea of **Docker-hosted services** and their interactions on kaiju.

## Docker Runtime

- **Engine:** Docker CE (official repo), **not** rootless — mailcow requires the root daemon
- **Management:** Portainer CE (web UI) for day-to-day container and stack management
- **Orchestration:** `docker compose` (Compose V2) for stacks (e.g. mailcow)

## Ingress and Certificate Strategy

- **Traefik** is the single reverse proxy for HTTP/HTTPS; certificate management by Traefik (or Certbot for edge cases)
- **Dual cert strategy:**
  - **Web services** (static site, etc.): Behind Cloudflare shield; use **Cloudflare Origin Certificates** (15-year, from Cloudflare dashboard). Traefik uses these as default TLS for the websecure entrypoint.
  - **Mail** (web UI, autoconfig, autodiscover): Use **Let's Encrypt** via Cloudflare DNS challenge (ACME). Certdumper copies these to mailcow for postfix/dovecot (SMTP/IMAPS direct access).
- Entrypoints: 80 (redirect to 443), 443
- Docker provider with `exposedByDefault: false` — only containers with Traefik labels are exposed
- Dashboard restricted to internal access (127.0.0.1:8080)

## Services

- **Mailcow** — full mail stack (SMTP, IMAP, webmail, etc.); see rule `mailcow` and `ansible/playbooks/mailcow.yml`. Web UI behind Traefik (and Cloudflare); SMTP/IMAPS direct with Let's Encrypt certs.
- **Static web** — nginx behind Traefik; behind Cloudflare shield; uses Cloudflare Origin Cert.

## Interaction Model

- Ansible deploys Docker, Portainer, Traefik, and base stacks; Mailcow is deployed via its own playbook
- All HTTP/HTTPS traffic to Dockerized apps goes through Traefik; do not bind host ports for HTTP except for Traefik’s 80/443
- Secrets (domain, API keys, mail passwords, origin certs) live in gitignored `group_vars/all.yml`; never commit them

## Domain

- **Host FQDN:** `kaiju.hell.sk`
- **Domain:** `hell.sk` — mail at `mail.hell.sk`, web at `www.hell.sk`
- DNS managed by Cloudflare

When adding or changing containers, ensure Traefik labels are correct and `exposedByDefault: false` is respected. Web services use default cert (origin); mail-related routers use `certresolver=cloudflare`.
