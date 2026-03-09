# Kaiju OS state

**Host FQDN:** `kaiju.hell.sk` | **Domain:** `hell.sk` | **DNS:** Cloudflare

Generated: 2026-03-07T22:05:28Z

## OS and kernel
```
Hostname: kaiju
ID=debian
VERSION=13 (trixie)
VERSION_CODENAME=trixie
Kernel: 6.1.0-18-amd64
Uptime: up 4 hours, 27 minutes
```

## CPU and memory
```
CPUs: 40
MemTotal: 65835888 kB
MemAvailable: 64754024 kB7
```

## Disks and mounts
```
NAME             SIZE TYPE  MOUNTPOINT FSTYPE
sda            446.6G disk
├─sda1           953M part  /boot      ext2
├─sda2           954M part  /boot/efi  vfat
└─sda3         444.8G part             crypto_LUKS
└─sda3_crypt 444.7G crypt /          btrfs
sdb              3.6T disk             crypto_LUKS
└─vault          3.6T crypt /vault     btrfs
zram0              4G disk  [SWAP]     swap
---
Filesystem              Size  Used Avail Use% Mounted on
udev                     32G     0   32G   0% /dev
tmpfs                   6.3G  2.1M  6.3G   1% /run
/dev/mapper/sda3_crypt  445G  2.3G  441G   1% /
tmpfs                    32G     0   32G   0% /dev/shm
tmpfs                   5.0M     0  5.0M   0% /run/lock
tmpfs                    32G     0   32G   0% /tmp
/dev/sda1               937M   34M  856M   4% /boot
/dev/sda2               953M  4.4M  948M   1% /boot/efi
/dev/mapper/vault       3.7T   19M  3.7T   1% /home
/dev/mapper/vault       3.7T   19M  3.7T   1% /vault
tmpfs                   6.3G   12K  6.3G   1% /run/user/1000
```

## Network (active interfaces, no MACs)
```
eno2 UP 
enp4s0f0 UP 
bond0 UP 10.101.10.74/24 10.101.10.73/24 fe80::1a66:daff:fe74:b19e/64
```

## btrfs subvolumes
```
--- / ---
--- /vault ---
```

## LUKS devices
```
NAME             SIZE FSTYPE      MOUNTPOINT
sda            446.6G
├─sda1           953M ext2        /boot
├─sda2           954M vfat        /boot/efi
└─sda3         444.8G crypto_LUKS
└─sda3_crypt 444.7G btrfs       /
sdb              3.6T crypto_LUKS
└─vault          3.6T btrfs       /vault
zram0              4G swap        [SWAP]
```

## systemd services (running, relevant)
```
cron.service               loaded active running Regular background program processing daemon
dbus.service               loaded active running D-Bus System Message Bus
getty@tty1.service         loaded active running Getty on tty1
rsyslog.service            loaded active running System Logging Service
serial-getty@ttyS0.service loaded active running Serial Getty on ttyS0
ssh.service                loaded active running OpenBSD Secure Shell server
systemd-journald.service   loaded active running Journal Service
systemd-logind.service     loaded active running User Login Management
systemd-timesyncd.service  loaded active running Network Time Synchronization
systemd-udevd.service      loaded active running Rule-based Manager for Device Events and Files
user@1000.service          loaded active running User Manager for UID 1000
```

## Docker
```
Docker not installed
```

## Relevant packages
```
ii  nftables       1.1.3-1      amd64        Program to control packet filtering rules by Netfilter project
ii  systemd-zram-generator 1.2.1-2      amd64        Systemd unit generator for zram devices
ii  btrfs-progs    6.14-1       amd64        Checksumming Copy on Write Filesystem utilities
```

