# Ansible playbooks for kaiju

Playbooks are run from your workstation (no direct SSH from automation). Copy the example files and fill in secrets.

**Host FQDNs:** `kaiju.hell.sk` (web), `mail.hell.sk` (mail) | **Domain:** `hell.sk` | **DNS:** Cloudflare

Single server with two IPs (e.g. bond0): web services and static sites on `web_ip` / `kaiju.hell.sk`, mail (Mailcow) on `mail_ip` / `mail.hell.sk`. One Traefik instance listens on both; routing is by hostname. Static content lives under `/var/www/html/<doc_root>/public`; configure `static_web_vhosts` in `group_vars/all.yml`.

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
# (optional) add production IPs on bond interface before DNS cutover
ansible-playbook -i inventory/hosts.yml playbooks/ip-migration.yml -t precheck,add_prod_ips
# (optional, after DNS cutover + validation) remove lab IPs
ansible-playbook -i inventory/hosts.yml playbooks/ip-migration.yml -t remove_lab_ips
ansible-playbook -i inventory/hosts.yml playbooks/observability.yml
```

Order: run `harden.yml` first, then `docker.yml`, then `mailcow.yml`.

## Playbooks

- **harden.yml** — SSH hardening, nftables firewall, fail2ban, unattended-upgrades, sysctl.
- **docker.yml** — Docker CE, Portainer, Traefik (dual cert: Cloudflare Origin for web, ACME for mail), multi-vhost static nginx from `/var/www/html`.
- **mailcow.yml** — mailcow-dockerized behind Traefik (mail, autodiscover, autoconfig, webmail/SOGo); requires Docker and Traefik. Restrict webmail by country via Cloudflare WAF if desired.
- **ip-migration.yml** — add production web/mail IPs to `bond0` alongside lab IPs, then (optionally) remove lab IPs after DNS cutover. Does **not** change persistent network config files; intended for controlled migration.
- **observability.yml** — Prometheus, Grafana, node_exporter, cAdvisor, Dozzle, and `ctop` for logs, metrics, and dashboards. Grafana at `{{ grafana_fqdn }}`, Dozzle at `{{ dozzle_fqdn }}` behind Traefik.

## Certificate strategy

- **Web services** (static site, etc.): Behind Cloudflare shield; use Cloudflare Origin Certificates (default TLS).
- **Mail** (SMTP, IMAPS, web UI, autoconfig, autodiscover): Let's Encrypt via Cloudflare DNS challenge; certdumper copies to mailcow for postfix/dovecot.
