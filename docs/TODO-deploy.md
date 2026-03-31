# Deployment TODO — kaiju.hell.sk (lab → production)

Comprehensive ordered checklist covering controller setup, lab provisioning, validation,
mailbox migration, and full production cutover.  
Mark items with `[x]` as you complete them.

---

## Phase 0 — Prerequisites (controller workstation)

### 0.1 Ansible installation
- [x] Install Ansible: `brew install ansible`
- [x] Verify: `ansible --version` (core 2.20.3)
- [x] Install required collections:
  ```bash
  ansible-galaxy collection install community.general
  ```
- [x] Install `htpasswd` utility (for generating Basic Auth hashes):
  ```bash
  # Debian/Ubuntu: apt install apache2-utils
  # macOS: brew install httpd
  htpasswd -nbB dominee 'YOUR_PASSWORD'
  ```
- [x] Install `imapsync` if running mailbox migration directly from controller:
  - Otherwise it runs on the server (done by the playbook)

### 0.2 Repository setup (controller)
- [x] Clone this repository:
  ```bash
  git clone git@github.com:<user>/kaiju-configs.git
  cd kaiju-configs/ansible
  ```
- [x] Create `inventory/hosts.yml` from example:
  ```bash
  cp inventory/hosts.yml.example inventory/hosts.yml
  ```
- [x] Create `group_vars/all.yml` from example:
  ```bash
  cp group_vars/all.yml.example group_vars/all.yml
  ```
- [x] Generate/place SSH key for `dominee` (if not yet done):
  ```bash
  ssh-keygen -t ed25519 -C "dominee@kaiju-deploy"
  ```
- [x] Place public key files in `ansible/files/ssh-keys/dominee/`:
  - One `.pub` file per key device/machine

### 0.3 Secrets and credentials

#### Cloudflare API token
- [x] Obtain Cloudflare API token (Zone.DNS Read+Write, Zone.Zone Read):
  - Cloudflare dashboard → My Profile → API Tokens → Create Token
  - Scope: `Zone.DNS — Edit`, `Zone.Zone — Read` for `hell.sk`

#### ansible-vault setup
- [x] Decide on secret management strategy: **ansible-vault** (file-level encryption)
- [x] Create a strong vault password and store it in your password manager
- [-] Wire vault password file into `ansible.cfg` (create if missing):
  ```bash
  cat > ansible/ansible.cfg <<'EOF'
  [defaults]
  vault_password_file = ~/keys/ansible/.ansible-vault-kaiju
  EOF
  ```
  - Alternatively pass `--vault-password-file ~/keys/ansible/.ansible-vault-kaiju` on each run
- [x] Verify vault tooling works:
  ```bash
  echo 'test' | ansible-vault encrypt_string --stdin-name test_var
  ```

#### Populate secrets in group_vars/all.yml
- [x] Set `cloudflare_api_token` using ansible-vault inline string:
  ```bash
  ansible-vault encrypt_string 'YOUR_CF_TOKEN' --name 'cloudflare_api_token'
  # Paste the output block into group_vars/all.yml
  ```
- [x] Set `grafana_admin_password`:
  ```bash
  ansible-vault encrypt_string 'YOUR_GRAFANA_PASSWORD' --name 'grafana_admin_password'
  ```
- [x] Generate htpasswd entry and set `observability_basic_auth_users`:
  ```bash
  htpasswd -nbB dominee 'YOUR_BASICAUTH_PASSWORD'
  # Copy the output (e.g. dominee:$2y$05$...) then:
  ansible-vault encrypt_string 'dominee:$2y$05$...' --name 'observability_basic_auth_users_0'
  ```
  - In `group_vars/all.yml` the final structure should be:
    ```yaml
    observability_basic_auth_users: !vault |
          $ANSIBLE_VAULT;1.1;AES256
          ...
    ```
- [x] Set `mailcow_dbpass`, `mailcow_dbroot`, `mailcow_redispass`, `mailcow_sogo_key`:
  - [-] **Option A (recommended for first install):** leave unset — playbook auto-generates them.
    After first run, copy values from `/root/mailcow.conf.initial` on the server and vault them.
  - [x] **Option B (reproducible installs):** pre-generate with `openssl rand -base64 24` and vault each.
- [x] Set `imapsync_accounts` (with passwords vaulted inline).
  - [x] Verify all vaulted variables decrypt and are readable:
  ```bash
  ansible -i inventory/hosts.yml localhost -m debug -a "var=cloudflare_api_token"
  ansible -i inventory/hosts.yml localhost -m debug -a "var=grafana_admin_password"
  ```

#### Inventory
- [x] Populate `inventory/hosts.yml`:
  - Set `ansible_host` to lab IP or `kaiju.hell.sk`
  - Set `ansible_user: dominee`
  - Set `ansible_ssh_private_key_file`

### 0.4 Managed node (kaiju) — initial OS access
- [x] Confirm SSH access with key:
  ```bash
  ssh dominee@10.101.10.73
  ```
- [x] Confirm `sudo` works for `dominee` without password (required for `become: true`):
  ```bash
  sudo -n true && echo ok
  ```
- [x] Confirm Python 3 is installed on managed node:
  ```bash
  python3 --version
  ```
- [x] If not: `sudo apt install -y python3`
- [x] Confirm Ansible can connect:
  ```bash
  ansible -i inventory/hosts.yml kaiju -m ping
  ```

---

## Phase 1 — Lab provisioning

### 1.1 Preflight validation
- [ ] Run preflight to check all required vars and host prerequisites:
  ```bash
  ansible-playbook -i inventory/hosts.yml playbooks/preflight.yml
  ```
- [ ] Confirm: all assertions pass, no failures

### 1.2 OS hardening
- [ ] Run harden playbook:
  ```bash
  ansible-playbook -i inventory/hosts.yml playbooks/harden.yml
  ```
- [ ] Verify SSH still accessible after firewall rules applied
- [ ] Verify `nftables` is running: `sudo nft list ruleset`
- [ ] Verify `fail2ban` is running: `sudo fail2ban-client status`

### 1.3 BTRFS subvolumes (before Docker)
- [ ] Review current BTRFS layout in `docs/kaiju-os-state.md`
- [ ] Run BTRFS subvolume conversion:
  ```bash
  ansible-playbook -i inventory/hosts.yml playbooks/btrfs-subvolumes.yml
  ```
- [ ] Verify subvolumes created:
  ```bash
  sudo btrfs subvolume list /
  ```
- [ ] Verify fstab entries:
  ```bash
  grep btrfs /etc/fstab
  ```
- [ ] Verify mounts survived service restarts (all services back up):
  ```bash
  sudo systemctl status docker
  ```

### 1.4 SSH key deployment
- [ ] Ensure public keys are in `ansible/files/ssh-keys/dominee/`
- [ ] Run ssh-keys playbook:
  ```bash
  ansible-playbook -i inventory/hosts.yml playbooks/ssh-keys.yml
  ```
- [ ] Test key login from all expected devices

### 1.5 Docker, Traefik, and static web
- [ ] Set DNS (lab): point `kaiju.hell.sk` → `10.101.10.73` in Cloudflare (or `/etc/hosts` for local testing)
- [ ] Run docker playbook:
  ```bash
  ansible-playbook -i inventory/hosts.yml playbooks/docker.yml
  ```
- [ ] Verify Docker running: `docker ps`
- [ ] Verify Traefik running: `docker ps | grep traefik`
- [ ] Verify static-web running: `docker ps | grep static-web`
- [ ] Test: `curl -k https://kaiju.hell.sk/` (or via `/etc/hosts`)
- [ ] Upload at least one placeholder page to `/var/www/html/hell.sk/public/index.html`
- [ ] Test static site for each vhost in `static_web_vhosts`

### 1.6 Mailcow deployment
- [ ] Ensure `/vault` is mounted and writable (LUKS decrypted)
- [ ] Run mailcow playbook:
  ```bash
  ansible-playbook -i inventory/hosts.yml playbooks/mailcow.yml
  ```
- [ ] Retrieve auto-generated secrets from `/root/mailcow.conf.initial` on the host
- [ ] Add those secrets to `group_vars/all.yml` (ansible-vault recommended)
- [ ] Verify Mailcow containers running:
  ```bash
  cd /vault/mailcow && docker compose ps
  ```
- [ ] Access Mailcow admin UI: `https://mail.hell.sk` (lab DNS or `/etc/hosts`)
- [ ] Set Mailcow admin password (first login)
- [ ] Create mailboxes for 3 users:
  - `dominee@hell.sk`
  - `djiabliq@hell.sk`
  - `celo@hell.sk`
- [ ] Verify IMAPS listening on `mail_ip`:
  ```bash
  ss -tln | grep 993
  ```
- [ ] Verify SMTP ports listening:
  ```bash
  ss -tln | grep -E '25|465|587'
  ```

### 1.7 Observability stack
- [ ] Confirm `observability_basic_auth_users` and `grafana_admin_password` are set
- [ ] Run observability playbook:
  ```bash
  ansible-playbook -i inventory/hosts.yml playbooks/observability.yml
  ```
- [ ] Verify containers running: `docker ps | grep -E 'prometheus|grafana|dozzle|cadvisor|node-exporter'`
- [ ] Access Grafana: `https://metrics.hell.sk` (lab DNS or `/etc/hosts`)
  - Login with `dominee` / `grafana_admin_password`
  - Add Prometheus data source: `http://prometheus:9090`
  - Import dashboards: Node Exporter Full (ID 1860), cAdvisor (ID 14282), Traefik v2/v3
- [ ] Access Dozzle: `https://logs.hell.sk` (verify Basic Auth prompt)
- [ ] Verify Basic Auth is enforced on both UIs (curl without creds should return 401)

---

## Phase 2 — Lab validation

### 2.1 Basic healthcheck
- [ ] Run basic healthcheck:
  ```bash
  ansible-playbook -i inventory/hosts.yml playbooks/healthcheck-basic.yml
  ```
- [ ] All critical services pass

### 2.2 Full healthcheck
- [ ] Run full healthcheck:
  ```bash
  ansible-playbook -i inventory/hosts.yml playbooks/healthcheck-full.yml \
    -e healthcheck_basic_auth_user=dominee \
    -e healthcheck_basic_auth_password='YOUR_PASSWORD'
  ```
- [ ] Traefik, Mailcow, Grafana, Dozzle HTTP checks pass
- [ ] Mail ports all confirmed listening

### 2.3 DNS (lab Cloudflare records)
- [ ] Set Cloudflare A records for lab IPs (DNS-only/unproxied for easy troubleshooting):
  - `kaiju.hell.sk` → `10.101.10.73`
  - `mail.hell.sk` → `10.101.10.74`
  - `autodiscover.hell.sk` → `10.101.10.74`
  - `autoconfig.hell.sk` → `10.101.10.74`
  - `webmail.hell.sk` → `10.101.10.74`
  - `metrics.hell.sk` → `10.101.10.73`
  - `logs.hell.sk` → `10.101.10.73`
  - static vhosts → `10.101.10.73`
- [ ] Run DNS automation to create/verify A records (safe — does NOT touch MX/SPF/DMARC):
  ```bash
  ansible-playbook -i inventory/hosts.yml playbooks/dns-cloudflare.yml
  # NOTE: mail-dns-records.yml is intentionally NOT run here.
  # MX/SPF/DMARC still point to abyss.hell.sk (production). Run it only at cutover.
  ansible-playbook -i inventory/hosts.yml playbooks/dns-validate.yml
  # Validates A records only (mail DNS validation is skipped by default during lab)
  ```
- [ ] All DNS validation assertions pass (A records only)

### 2.4 TLS certificate validation
- [x] Cloudflare Origin Cert (if `cloudflare_origin_cert_enabled: true`):
  - [x] Generate Origin Cert in Cloudflare dashboard (SSL/TLS → Origin Server)
  - [ ] Place `origin.pem` and `origin-key.pem` in `/opt/traefik/certs/`
  - [ ] Redeploy Traefik: re-run `docker.yml`
- [ ] ACME certs (mail hostnames):
  - [ ] Confirm `acme.json` populated (Traefik has issued certs):
    ```bash
    cat /opt/traefik/letsencrypt/acme.json | python3 -m json.tool | grep -E '"domain"|"main"'
    ```
  - [ ] Confirm no cert errors in Traefik logs:
    ```bash
    docker logs traefik 2>&1 | grep -i 'error\|acme\|certif'
    ```

### 2.5 Mail flow validation (lab)
- [ ] Send test email from `dominee@hell.sk` to an external address
- [ ] Send test email to `dominee@hell.sk` from external
- [ ] Confirm DKIM signing (check headers of received mail)
- [ ] Confirm SPF passes (check headers)
- [ ] Validate DMARC policy (use `https://mxtoolbox.com/dmarc.aspx`)
- [ ] Test autodiscover from a mail client (Outlook/Thunderbird)
- [ ] Test SOGo webmail: `https://webmail.hell.sk`

### 2.6 Mailbox pre-migration (lab — first sync from abyss)
- [ ] Ensure abyss.hell.sk is reachable on IMAPS/993
- [ ] Configure imapsync credentials in `group_vars/all.yml` (ansible-vault)
- [ ] Run dry-run first:
  ```bash
  ansible-playbook -i inventory/hosts.yml playbooks/mailbox-migration-imapsync.yml \
    -e imapsync_dry_run=true
  ```
- [ ] Review dry-run output for expected folder/message counts
- [ ] Run actual pre-migration sync:
  ```bash
  ansible-playbook -i inventory/hosts.yml playbooks/mailbox-migration-imapsync.yml
  ```
- [ ] Verify mailboxes appear in Mailcow/SOGo for all 3 users

---

## Phase 3 — Production cutover

### 3.1 Prepare production IPs
- [ ] Confirm production web IP and mail IP are allocated (e.g. from ISP/data centre)
- [ ] Update `group_vars/all.yml`: set `web_ip` and `mail_ip` to production values
- [ ] Add production IPs to the server (alongside lab IPs):
  ```bash
  ansible-playbook -i inventory/hosts.yml playbooks/ip-migration.yml \
    -e prod_web_ip=<PROD_WEB_IP>/24 \
    -e prod_mail_ip=<PROD_MAIL_IP>/24 \
    -t precheck,add_prod_ips
  ```
- [ ] Verify both lab and production IPs are active:
  ```bash
  ip -4 addr show bond0
  ```
- [ ] Test services are reachable on production IPs (before DNS cut):
  ```bash
  curl -k --resolve kaiju.hell.sk:443:<PROD_WEB_IP> https://kaiju.hell.sk/
  curl -k --resolve mail.hell.sk:443:<PROD_MAIL_IP> https://mail.hell.sk/
  ```

### 3.2 Pre-cutover final delta sync (mailboxes)
- [ ] Run mailbox delta sync (last sync before DNS cut):
  ```bash
  ansible-playbook -i inventory/hosts.yml playbooks/mailbox-migration-imapsync.yml
  ```
- [ ] Confirm message counts are current for all 3 mailboxes

### 3.3 DNS cutover (Cloudflare)
- [ ] Update Cloudflare A records to production IPs:
  ```bash
  ansible-playbook -i inventory/hosts.yml playbooks/dns-cloudflare.yml
  ```
  (or manually in Cloudflare dashboard if you prefer point-in-time control)
- [ ] **Cut mail DNS over to kaiju** — only after imapsync final sync, mailcow confirmed healthy:
  ```bash
  # This WILL overwrite MX/SPF/DMARC. abyss.hell.sk will stop receiving mail immediately.
  ansible-playbook -i inventory/hosts.yml playbooks/mail-dns-records.yml -e mail_dns_cutover_ready=true
  ```
- [ ] Validate post-cutover (A records + mail DNS):
  ```bash
  ansible-playbook -i inventory/hosts.yml playbooks/dns-validate.yml -e validate_mail_dns=true
  ```
- [ ] Set appropriate proxy mode:
  - Web hostnames: **Proxied** (Cloudflare shield + Origin Cert)
  - Mail hostnames: **DNS-only** (SMTP/IMAPS cannot be proxied)
- [ ] Run DNS validation:
  ```bash
  ansible-playbook -i inventory/hosts.yml playbooks/dns-validate.yml
  ```
- [ ] Wait for TTL propagation (typically 1–5 min with Cloudflare; confirm with `dig`)

### 3.4 Post-cutover validation
- [ ] Confirm all web vhosts respond on production IPs:
  - `https://kaiju.hell.sk`, `https://hell.sk`, `https://www.hell.sk`, `https://from.hell.sk`
  - `https://goldendawns-clan.cz`, `https://www.goldendawns-clan.cz`
- [ ] Confirm mail UI: `https://mail.hell.sk`, `https://webmail.hell.sk`
- [ ] Confirm observability UIs: `https://metrics.hell.sk`, `https://logs.hell.sk`
- [ ] Run full healthcheck:
  ```bash
  ansible-playbook -i inventory/hosts.yml playbooks/healthcheck-full.yml \
    -e healthcheck_validate_certs=true \
    -e healthcheck_basic_auth_user=dominee \
    -e healthcheck_basic_auth_password='YOUR_PASSWORD'
  ```
- [ ] Test inbound mail delivery to all 3 accounts
- [ ] Test outbound mail from all 3 accounts
- [ ] Check Grafana dashboards for post-cutover anomalies

### 3.5 Post-cutover mailbox delta sync (optional)
- [ ] After old server is confirmed offline or in lab:
  - Run final delta sync:
    ```bash
    ansible-playbook -i inventory/hosts.yml playbooks/mailbox-migration-imapsync.yml
    ```
  - Verify no messages missed

### 3.6 DKIM configuration
- [ ] Extract DKIM public key from Mailcow admin UI:
  - Mail Setup → Domains → hell.sk → DKIM → Show Public Key
- [ ] Add to `group_vars/all.yml`:
  ```yaml
  dkim_selector: "dkim"
  dkim_public_key: "v=DKIM1; k=rsa; p=MIIB..."
  ```
- [ ] Push DKIM TXT record to Cloudflare (requires cutover flag since DKIM is managed by the same playbook):
  ```bash
  ansible-playbook -i inventory/hosts.yml playbooks/mail-dns-records.yml -e mail_dns_cutover_ready=true
  ```
- [ ] Validate DKIM signing on next outbound email (check headers)
- [ ] After DKIM/SPF/DMARC all validated, tighten DMARC policy:
  - `dmarc_policy: "quarantine"` → then `"reject"` after monitoring

### 3.7 Remove lab IPs (final cleanup)
- [ ] Confirm all production services stable for at least 24–48 hours
- [ ] Confirm no client is still using lab IPs (check server logs)
- [ ] Remove lab IPs from the server:
  ```bash
  ansible-playbook -i inventory/hosts.yml playbooks/ip-migration.yml \
    -e prod_web_ip=<PROD_WEB_IP>/24 \
    -e prod_mail_ip=<PROD_MAIL_IP>/24 \
    -e lab_web_ip=10.101.10.73/24 \
    -e lab_mail_ip=10.101.10.74/24 \
    -t remove_lab_ips
  ```
- [ ] Verify only production IPs remain on `bond0`:
  ```bash
  ip -4 addr show bond0
  ```
- [ ] Update `group_vars/all.yml` to reflect final `web_ip` and `mail_ip`

---

## Phase 4 — Post-production hardening and tidy-up

### 4.1 Cloudflare WAF (webmail geoip restriction)
- [ ] Log in to Cloudflare dashboard
- [ ] Create WAF rule for `webmail.hell.sk`:
  - Match: `(http.host eq "webmail.hell.sk") and not (ip.geoip.country in {"SK" "CZ"})`
  - Action: Block
- [ ] Test restriction: confirm access from allowed country, confirm block from other

### 4.2 Secrets audit
- [ ] Confirm `group_vars/all.yml` is in `.gitignore` / never committed
- [ ] Confirm `inventory/hosts.yml` is in `.gitignore` / never committed
- [ ] Vault all remaining plaintext secrets in `group_vars/all.yml`:
  ```bash
  ansible-vault encrypt group_vars/all.yml
  ```
- [ ] Test vault decryption:
  ```bash
  ansible-vault view group_vars/all.yml
  ```
- [ ] Store vault password securely (password manager, not in repo)

### 4.3 BTRFS snapshot baseline
- [ ] Take a post-production baseline BTRFS snapshot of all subvolumes:
  - `@root`, `@vault`, `@var_lib_docker`, `@var_www_html`, `@var_log`, `@home`
  - (snapshot playbook to be added — see planned `btrfs-snapshot.yml`)
- [ ] Document snapshot labels in `docs/kaiju-os-state.md`

### 4.4 Monitoring baseline
- [ ] Confirm Prometheus is collecting metrics from all targets:
  - Visit `http://prometheus:9090/targets` via Grafana or SSH tunnel
  - All targets should show "UP"
- [ ] Set up basic Grafana alerting (optional but recommended):
  - Alert if node is unreachable
  - Alert if disk usage > 80%
  - Alert if a core container is not running

### 4.5 Final documentation
- [ ] Update `docs/kaiju-os-state.md` with:
  - Final BTRFS subvolume layout
  - Production IP addresses
  - Installed software versions
- [ ] Commit all config changes (no secrets) to the repository:
  ```bash
  git add .
  git commit -m "chore: post-production baseline config"
  git push
  ```
- [ ] Archive `/root/mailcow.conf.initial` from the server to a secure, offline location
- [ ] Remove `/root/mailcow.conf.initial` from the server once safely archived:
  ```bash
  sudo shred -u /root/mailcow.conf.initial
  ```

---

## Quick reference: playbook run order

```text
# Phase 0 (controller, one-time)
pip install ansible
ansible -i inventory/hosts.yml kaiju -m ping

# Phase 1 (lab)
ansible-playbook -i inventory/hosts.yml playbooks/preflight.yml
ansible-playbook -i inventory/hosts.yml playbooks/harden.yml
ansible-playbook -i inventory/hosts.yml playbooks/btrfs-subvolumes.yml
ansible-playbook -i inventory/hosts.yml playbooks/ssh-keys.yml
ansible-playbook -i inventory/hosts.yml playbooks/docker.yml
ansible-playbook -i inventory/hosts.yml playbooks/mailcow.yml
ansible-playbook -i inventory/hosts.yml playbooks/observability.yml
ansible-playbook -i inventory/hosts.yml playbooks/dns-cloudflare.yml
# NOTE: mail-dns-records.yml is NOT run here — MX/SPF/DMARC are only pushed at production cutover
# ansible-playbook -i inventory/hosts.yml playbooks/mail-dns-records.yml -e mail_dns_cutover_ready=true

# Phase 2 (lab validation)
ansible-playbook -i inventory/hosts.yml playbooks/healthcheck-basic.yml
ansible-playbook -i inventory/hosts.yml playbooks/healthcheck-full.yml
ansible-playbook -i inventory/hosts.yml playbooks/dns-validate.yml
# mail DNS validation is skipped by default; add -e validate_mail_dns=true post-cutover
ansible-playbook -i inventory/hosts.yml playbooks/mailbox-migration-imapsync.yml -e imapsync_dry_run=true
ansible-playbook -i inventory/hosts.yml playbooks/mailbox-migration-imapsync.yml

# Phase 3 (production cutover)
ansible-playbook -i inventory/hosts.yml playbooks/ip-migration.yml -e prod_web_ip=... -e prod_mail_ip=... -t precheck,add_prod_ips
ansible-playbook -i inventory/hosts.yml playbooks/mailbox-migration-imapsync.yml   # final pre-cutover delta
ansible-playbook -i inventory/hosts.yml playbooks/dns-cloudflare.yml               # switch to prod IPs
ansible-playbook -i inventory/hosts.yml playbooks/dns-validate.yml
ansible-playbook -i inventory/hosts.yml playbooks/healthcheck-full.yml -e healthcheck_validate_certs=true ...
ansible-playbook -i inventory/hosts.yml playbooks/mailbox-migration-imapsync.yml   # post-cutover delta
ansible-playbook -i inventory/hosts.yml playbooks/ip-migration.yml ... -t remove_lab_ips
```
