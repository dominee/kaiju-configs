# Ansible playbooks for kaiju

Playbooks are run from your workstation (no direct SSH from automation). Copy the example files and fill in secrets.

**Host FQDNs:** `kaiju.hell.sk` (web), `mail.hell.sk` (mail) | **Domain:** `hell.sk` | **DNS:** Cloudflare

Single server with two IPs (e.g. bond0): web services and static sites on `web_ip` / `kaiju.hell.sk`, mail (Mailcow) on `mail_ip` / `mail.hell.sk`. One Traefik instance listens on both; routing is by hostname. Static content lives under `/var/www/html/<doc_root>/public`; configure `static_web_vhosts` in `group_vars/all.yml`.

## Setup

1. Copy the example inventory and group_vars (do not commit the real files):

   ```bash
   cp inventory/hosts.yml.example inventory/hosts.yml
   cp group_vars/all.yml.example group_vars/all.yml
   ```

2. Edit `inventory/hosts.yml` with the server IP/hostname (`kaiju.hell.sk` or IP) and SSH user/key.
3. Edit `group_vars/all.yml` with domain, Cloudflare API token, and any mailcow settings.
4. **Cloudflare Origin Cert:** For web services behind Cloudflare shield, create an Origin Certificate in Cloudflare (SSL/TLS > Origin Server > Create Certificate) and place `origin.pem` and `origin-key.pem` in `/opt/traefik/certs/` on the server. Or set `cloudflare_origin_cert_enabled: false` to use ACME for all services.

## Run playbooks

From the repository root:

```bash
cd ansible
ansible-playbook -i inventory/hosts.yml playbooks/harden.yml
ansible-playbook -i inventory/hosts.yml playbooks/docker.yml
ansible-playbook -i inventory/hosts.yml playbooks/mailcow.yml
```

Order: run `harden.yml` first, then `docker.yml`, then `mailcow.yml`.

## Playbooks

- **harden.yml** — SSH hardening, nftables firewall, fail2ban, unattended-upgrades, sysctl.
- **docker.yml** — Docker CE, Portainer, Traefik (dual cert: Cloudflare Origin for web, ACME for mail), multi-vhost static nginx from `/var/www/html`.
- **mailcow.yml** — mailcow-dockerized behind Traefik (mail, autodiscover, autoconfig, webmail/SOGo); requires Docker and Traefik. Restrict webmail by country via Cloudflare WAF if desired.

## Certificate strategy

- **Web services** (static site, etc.): Behind Cloudflare shield; use Cloudflare Origin Certificates (default TLS).
- **Mail** (SMTP, IMAPS, web UI, autoconfig, autodiscover): Let's Encrypt via Cloudflare DNS challenge; certdumper copies to mailcow for postfix/dovecot.
