# Ansible playbooks for kaiju

Playbooks are run from your workstation (no direct SSH from automation). Copy the example files and fill in secrets.

**Host FQDNs:** `kaiju.hell.sk` (web), `mail.hell.sk` (mail) | **Domain:** `hell.sk` | **DNS:** Cloudflare

Single server with two IPs (e.g. bond0): web services and static sites on `web_ip` / `kaiju.hell.sk`, mail (Mailcow) on `mail_ip` / `mail.hell.sk`. One Traefik instance listens on both; routing is by hostname. Static content lives under `/var/www/html/<doc_root>/public`; configure `static_web_vhosts` in `group_vars/all.yml`.

All hosts referenced by this repository and targeted by these playbooks are assumed to be under the **`hell.sk`** domain.

## Hostnames and IPs (`*.hell.sk`)

Lab (example) mapping on one server (bond0 with two IPs):

- **Web IP (`web_ip`)**: `10.101.10.73`
  - **`kaiju.hell.sk`** → `10.101.10.73` (Traefik + static web)
  - **`hell.sk` / `www.hell.sk` / `from.hell.sk`** → `10.101.10.73` (static sites via Traefik)
- **Mail IP (`mail_ip`)**: `10.101.10.74`
  - **`mail.hell.sk`** → `10.101.10.74` (Mailcow UI + mail endpoints)
  - **`autodiscover.hell.sk`** → `10.101.10.74` (Mailcow autodiscover)
  - **`autoconfig.hell.sk`** → `10.101.10.74` (Mailcow autoconfig)
  - **`webmail.hell.sk`** → `10.101.10.74` (SOGo; restrict by geoip via Cloudflare WAF)

Notes:

- Traefik is a **single instance**; separation is by **hostname** and (externally) by **which IP Cloudflare points each hostname at**.
- Mailcow also exposes non-HTTP ports (SMTP/IMAP/etc.) and those should be reachable on the **mail IP**.

## Recommended lab → production cutover (IP change)

- **Prepare production IPs**
  - Allocate/confirm the new **web IP** and **mail IP**.
  - Add them to `bond0` (or the appropriate interface) on the server.
  - Update `group_vars/all.yml` (`web_ip`, `mail_ip`) if you use them operationally/documentation-wise.
- **Verify services bind/listen correctly**
  - Ensure HTTP(S) (`80/443`) is reachable and Traefik routes:
    - Web hostnames on the **web IP**
    - Mail/webmail/autodiscover/autoconfig on the **mail IP**
  - Ensure mail ports (25/465/587/143/993/110/995/4190) are reachable on the **mail IP**.
- **Cut DNS in Cloudflare**
  - Update A/AAAA records for `kaiju.hell.sk` and all web/static hostnames to the **production web IP**.
  - Update A/AAAA records for `mail.hell.sk`, `webmail.hell.sk`, `autodiscover.hell.sk`, `autoconfig.hell.sk` to the **production mail IP**.
  - If you use Cloudflare proxying, keep the proxy mode consistent with your certificate strategy (Origin Cert for web, ACME for mail).
- **Post-cutover checks**
  - Confirm TLS is valid for web and mail hostnames.
  - Confirm inbound/outbound mail flow and client autoconfig/autodiscover.
  - Only after stability, remove the old lab IPs from the interface.

## Setup

1. Copy the example inventory and group_vars (do not commit the real files):

   ```bash
   cp inventory/hosts.yml.example inventory/hosts.yml
   cp group_vars/all.yml.example group_vars/all.yml
   ```

   Keep your real vars in `ansible/group_vars/all.yml`. The committed symlink
   `inventory/group_vars/all.yml` → `../../group_vars/all.yml` exists so Ansible’s
   **inventory-adjacent** `group_vars` resolution still finds that file. Without it, running
   `ansible-playbook` from the **repository root** (e.g. `-i ansible/inventory/hosts.yml`) would
   not load `ansible/group_vars/all.yml`, and plays would see undefined `domain`,
   Cloudflare vars, etc. Running from `ansible/` with `-i inventory/hosts.yml` can mask
   that, because Ansible also discovers `group_vars` relative to the current working directory.

2. Edit `inventory/hosts.yml` with the server IP/hostname (`kaiju.hell.sk` or IP) and SSH user/key.
3. Edit `group_vars/all.yml` with domain, scoped Cloudflare API tokens (`cloudflare_acme_dns_token`, `cloudflare_dns_api_token`, or legacy `cloudflare_api_token`), and any mailcow settings.
4. **Cloudflare Origin Cert:** For web services behind Cloudflare shield, create an Origin Certificate in Cloudflare (SSL/TLS > Origin Server > Create Certificate) and place `origin.pem` and `origin-key.pem` in `/opt/traefik/certs/` on the server. Or set `cloudflare_origin_cert_enabled: false` to use ACME for all services.

## Run playbooks

From the repository root:

```bash
cd ansible
ansible-playbook -i inventory/hosts.yml playbooks/preflight.yml
ansible-playbook -i inventory/hosts.yml playbooks/harden.yml
ansible-playbook -i inventory/hosts.yml playbooks/docker.yml
ansible-playbook -i inventory/hosts.yml playbooks/mailcow.yml
# (optional) add production IPs on bond interface before DNS cutover
ansible-playbook -i inventory/hosts.yml playbooks/ip-migration.yml -t precheck,add_prod_ips
# (optional, after DNS cutover + validation) remove lab IPs
ansible-playbook -i inventory/hosts.yml playbooks/ip-migration.yml -t remove_lab_ips
ansible-playbook -i inventory/hosts.yml playbooks/observability.yml
ansible-playbook -i inventory/hosts.yml playbooks/healthcheck-basic.yml
ansible-playbook -i inventory/hosts.yml playbooks/healthcheck-full.yml
```

Order: run `harden.yml` first, then `docker.yml`, then `mailcow.yml`.

## Playbooks

- **harden.yml** — SSH hardening, nftables firewall, fail2ban, unattended-upgrades, sysctl.
- **docker.yml** — Docker (CE when available; falls back to Debian `docker.io`), Traefik (dual cert: Cloudflare Origin for web, ACME for mail), multi-vhost static nginx from `/var/www/html`.
- **mailcow.yml** — mailcow-dockerized behind Traefik (mail, autodiscover, autoconfig, webmail/SOGo); requires Docker and Traefik. Restrict webmail by country via Cloudflare WAF if desired.
- **ip-migration.yml** — add production web/mail IPs to `bond0` alongside lab IPs, then (optionally) remove lab IPs after DNS cutover. Does **not** change persistent network config files; intended for controlled migration.
- **observability.yml** — Prometheus, Grafana, node_exporter, cAdvisor, Dozzle, and `ctop` for logs, metrics, and dashboards. Grafana at `{{ grafana_fqdn }}`, Dozzle at `{{ dozzle_fqdn }}` behind Traefik.
- Observability UIs (`metrics.*`, `logs.*`) are protected with Traefik **Basic Auth** (configure `observability_basic_auth_users` in `group_vars/all.yml`, ideally via ansible-vault).
- **btrfs-subvolumes.yml** — convert existing directories (`/var/lib/docker`, `/var/www/html`, `/var/log`, `/home`) into dedicated BTRFS subvolumes on a running system, updating fstab and mounts. Designed for the kaiju host layout in `docs/kaiju-os-state.md`.
- **ssh-keys.yml** — deploy SSH `authorized_keys` for `dominee` from all public key files in `ansible/files/ssh-keys/dominee/`.
- **healthcheck-basic.yml** — basic OS and Docker health: uptime, load, disk, memory, critical systemd services, and running containers.
- **healthcheck-full.yml** — extended healthcheck including BTRFS status, Traefik/Mailcow/observability containers, HTTP checks for key UIs, and listening mail ports.
- **mailbox-migration-imapsync.yml** — migrate IMAP mailboxes from `abyss.hell.sk` (Dovecot) to Mailcow using `imapsync`; safe to re-run for delta sync (store passwords via ansible-vault).
- **dns-cloudflare.yml** — create/update **core** A records in Cloudflare for the primary zone (kaiju/mail/webmail/autoconfig/autodiscover/metrics/logs) plus **`static_web_vhosts` FQDNs under that zone that are not in the production-static list** (see below). Gated by explicit flags so a shared zone is not overwritten by accident.
- **mail-dns-records.yml** — create/update mail DNS essentials in Cloudflare (MX/SPF/DMARC and optional DKIM TXT) for `hell.sk`.
- **dns-validate.yml** — validate Cloudflare DNS against `group_vars` for the same core A records; optional static vhosts under the zone (respecting the production-static list); mail records only if `validate_mail_dns=true`.

### Cloudflare DNS automation (`dns-cloudflare.yml` / `dns-validate.yml`)

**Core hostnames** (always included when the playbooks run): `kaiju`, `mail`, `autodiscover`, `autoconfig`, `webmail`, `metrics`, `logs` (FQDNs from `group_vars`, usually `*.hell.sk`). They are validated and, when you apply DNS, managed toward `web_ip` / `mail_ip`.

**Production-static static sites** (default FQDNs: apex `domain`, `www.` + `domain`, `from.` + `domain`, plus `goldendawns-clan.cz` / `www.goldendawns-clan.cz` — override with `dns_production_static_fqdns`):

- With **`dns_production_static_allow_changes: false`** (default): `dns-validate.yml` does **not** expect their A records to match `web_ip`; `dns-cloudflare.yml` does **not** create or update them from `static_web_vhosts`. Same idea as skipping mail DNS validation until cutover.
- Set **`dns_production_static_allow_changes: true`** when those names should follow `web_ip` like the core web stack (e.g. after production cutover).

**Apply gates (`dns-cloudflare.yml` only):**

- **`dns_core_apply_ready: true`** (required) — without it the playbook exits before any Cloudflare write.
- **`cloudflare_allow_updates: true`** — allow **PUT** when an existing record differs (IP, TTL, proxied). If false, drift **fails** the play instead of overwriting. **POST** (create missing record) is still allowed when the play runs; excluded FQDNs never reach this logic.

**Proxy / lab DNS-only:**

- **`cf_web_a_proxied`** — expected Cloudflare proxy for kaiju, metrics, logs, and non–production-static static A records (`true` = orange cloud, `false` = DNS-only, typical in lab).
- **`cf_webmail_proxied`** — proxy flag for the webmail A record only.

Example (lab: write core A records to Cloudflare, DNS-only, no updates to existing rows):

```bash
ansible-playbook -i inventory/hosts.yml playbooks/dns-cloudflare.yml \
  -e dns_core_apply_ready=true
# Add -e cloudflare_allow_updates=true when you intend to overwrite differing records.
```

Validate without touching production-static apex/www/from (default):

```bash
ansible-playbook -i inventory/hosts.yml playbooks/dns-validate.yml
```
- **preflight.yml** — validate required variables and prerequisites before deploying (scoped Cloudflare API tokens or legacy single token, IP/FQDNs, Origin cert presence when enabled, observability auth, Grafana admin password, mailcow path).

## Certificate strategy

- **Web services** (static site, etc.): Behind Cloudflare shield; use Cloudflare Origin Certificates (default TLS).
- **Mail** (SMTP, IMAPS, web UI, autoconfig, autodiscover): Let's Encrypt via Cloudflare DNS challenge; certdumper copies to mailcow for postfix/dovecot.
- **Cloudflare credentials:** Use scoped **API Tokens** — `cloudflare_acme_dns_token` in `.env` for Traefik ACME, and `cloudflare_dns_api_token` for DNS playbooks (see `group_vars/all.yml.example`). A single legacy `cloudflare_api_token` can still back both until you split.
