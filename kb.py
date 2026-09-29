"""
kb.py -- Knowledge Base for the NetDiag Expert System
=======================================================

Knowledge representation choice: PRODUCTION RULES (IF-THEN), Boolean-valued.

Why rules (and not frames or semantic nets) for this domain:
- The domain is diagnostic troubleshooting: chains of "symptom implies cause"
  reasoning, which maps directly onto antecedent -> consequent rules.
- Rules chain naturally into multi-step derivations (a rule's conclusion can
  be another rule's condition), which is exactly what both forward and
  backward chaining need to demonstrate.
- Rules are the most explainable representation available: a fired rule can
  be read back to the user almost verbatim ("Because X and Y, therefore Z"),
  which directly satisfies the explainability requirement.
- Frames would suit a domain organised around structured *objects* with
  slots/inheritance (e.g. classifying router models); semantic nets suit
  domains about *relationships* between concepts. Neither fits a domain whose
  expertise is fundamentally "if these symptoms hold, suspect this fault".

Every condition is a fact id, optionally prefixed with "!" to mean
"this fact must be False" (negation as failure over the known-fact set).

A fact can be:
  - ASKABLE  -> a leaf fact the system will ask the user about directly.
  - INTERMEDIATE -> only ever derived by a rule (never asked), used to
                    represent partial diagnostic hypotheses (e.g.
                    "suspect_dns_issue") so multi-step chaining is real,
                    not just cosmetic.
  - DIAGNOSIS -> a derived fact that is a final, reportable conclusion, with
                 a human-readable recommendation attached.
"""

# ---------------------------------------------------------------------------
# 1. ASKABLE FACTS  (30 leaf facts the system can ask the user about)
# ---------------------------------------------------------------------------
FACTS = {
    "no_internet_access":        "Are you unable to access the internet on this device?",
    "power_light_on":            "Is the router's power light on?",
    "wifi_light_on":             "Is the router's WiFi/wireless indicator light on?",
    "ethernet_connected":        "Is the device connected via an Ethernet cable?",
    "wifi_connected":            "Is the device connected via WiFi?",
    "can_ping_router":           "Can you successfully ping the router's local IP (e.g. 192.168.1.1)?",
    "can_ping_external_ip":      "Can you successfully ping an external IP address (e.g. 8.8.8.8)?",
    "can_resolve_dns":           "Can you successfully resolve domain names (e.g. ping google.com works)?",
    "multiple_devices_affected": "Are other devices on the same network also affected?",
    "router_recently_rebooted":  "Has the router been rebooted in the last 10 minutes?",
    "ip_address_assigned":       "Does the device have a valid IP address assigned (not a 169.254.x.x address)?",
    "ip_conflict_error":         "Has the OS shown an 'IP address conflict' error?",
    "vpn_active":                "Is a VPN connection currently active on the device?",
    "proxy_configured":          "Is a proxy server configured in the network settings?",
    "firewall_recently_changed": "Were firewall settings changed recently?",
    "antivirus_blocking_notification": "Has the antivirus/security software shown a network-blocking notification recently?",
    "browser_dns_error_shown":   "Does the browser show a DNS-related error (e.g. DNS_PROBE_FINISHED)?",
    "system_slow":               "Is the system running noticeably slower than usual?",
    "high_cpu_usage":            "Is CPU usage abnormally high (Task Manager shows over 85%)?",
    "high_disk_usage":           "Is disk usage abnormally high (near 100%)?",
    "low_disk_space":            "Is available free disk space below 10%?",
    "malware_scan_flagged":      "Did a recent malware/antivirus scan flag any threats?",
    "driver_outdated":           "Are the network adapter drivers outdated (not updated in 6+ months)?",
    "os_recently_updated":       "Was the operating system updated in the last 24 hours?",
    "overheating_detected":      "Does the device feel unusually hot, or is the fan running at max speed constantly?",
    "blue_screen_recently":      "Has the system experienced a crash/blue screen recently?",
    "cable_damage_visible":      "Is there any visible damage to the network cable?",
    "signal_strength_weak":      "Is the WiFi signal strength shown as weak or poor?",
    "new_software_installed":    "Was new software or an update installed just before the issue started?",
    "disk_check_errors":         "Does a disk check (chkdsk / SMART status) show errors?",
}

# ---------------------------------------------------------------------------
# 2. INTERMEDIATE FACTS  (derived only, never asked; give the KB real depth)
# ---------------------------------------------------------------------------
INTERMEDIATE_LABELS = {
    "suspect_router_fault":          "Router hardware is suspected of being at fault",
    "suspect_local_config_issue":    "A local network configuration issue is suspected",
    "suspect_dns_issue":             "A DNS resolution issue is suspected",
    "suspect_resource_heavy_process": "An unusually resource-heavy process is suspected",
}

# ---------------------------------------------------------------------------
# 3. DIAGNOSES  (final, reportable conclusions with recommendations)
# ---------------------------------------------------------------------------
DIAGNOSES = {
    "router_powered_off":            ("Router is powered off",
                                       "Check that the router is plugged in and switched on at the wall."),
    "router_hardware_fault":         ("Router hardware fault",
                                       "The router is on but not responding even after a reboot. It likely needs replacement or vendor support."),
    "isp_outage":                    ("ISP outage",
                                       "Your router is reachable but the wider internet is not, and other devices are affected too. Contact your ISP."),
    "ip_address_conflict":           ("IP address conflict",
                                       "Two devices on the network have the same IP. Release/renew the IP lease or set a static IP."),
    "dhcp_failure":                  ("DHCP failure",
                                       "The device did not get a valid IP address. Restart the DHCP client or check the router's DHCP server."),
    "dns_failure":                   ("DNS resolution failure",
                                       "You can reach the internet by IP but not by domain name. Try a different DNS server (e.g. 1.1.1.1 or 8.8.8.8)."),
    "vpn_dns_conflict":              ("VPN causing DNS conflict",
                                       "The active VPN is likely overriding DNS settings. Try disconnecting the VPN or changing its DNS configuration."),
    "faulty_cable":                  ("Faulty Ethernet cable",
                                       "Visible cable damage was reported. Replace the Ethernet cable."),
    "weak_wifi_signal":              ("Weak WiFi signal",
                                       "Move closer to the router, remove obstructions, or consider a WiFi extender."),
    "proxy_misconfiguration":        ("Proxy misconfiguration",
                                       "A configured proxy is likely blocking traffic. Verify or disable the proxy settings."),
    "firewall_blocking":             ("Firewall blocking traffic",
                                       "Recent firewall changes are likely blocking network traffic. Review the latest firewall rule changes."),
    "antivirus_blocking_network":    ("Antivirus/security software blocking network",
                                       "The security suite raised a network-blocking alert. Check its network protection / firewall module."),
    "new_software_resource_conflict": ("Resource conflict from newly installed software",
                                       "A recently installed program is likely consuming excess resources. Check Task Manager and consider uninstalling it."),
    "malware_infection":             ("Possible malware infection",
                                       "A scan flagged threats while performance dropped. Run a full malware removal and update definitions."),
    "low_disk_space_slowdown":       ("Slowdown due to low disk space",
                                       "Free disk space is critically low. Delete unnecessary files or expand storage."),
    "failing_disk":                  ("Failing disk drive",
                                       "High disk usage combined with disk check errors suggests the drive is failing. Back up data immediately and run full diagnostics."),
    "outdated_driver_performance_issue": ("Outdated network/device driver",
                                       "Outdated drivers are a likely cause of the slowdown. Update drivers via the manufacturer's site."),
    "post_update_instability":       ("Post-update instability",
                                       "Slowness began after a recent OS update with no other cause found. Allow indexing to finish, or consider rolling back the update."),
    "thermal_throttling":            ("Thermal throttling",
                                       "High CPU usage combined with overheating suggests the CPU is throttling itself. Improve cooling/ventilation and clean dust from vents."),
    "driver_crash":                  ("Crash caused by outdated driver",
                                       "The blue screen is likely caused by an outdated driver. Update or roll back the relevant driver."),
    "hardware_overheating_crash":    ("Crash caused by overheating",
                                       "The blue screen is likely caused by thermal issues. Check cooling, fans, and thermal paste."),
    "disk_failure_crash":            ("Crash caused by failing disk",
                                       "The blue screen is likely caused by a failing disk. Back up data and replace the drive."),
    "router_wifi_radio_disabled":    ("Router WiFi radio disabled",
                                       "The router's WiFi light is off while wired connections may still work. Re-enable the WiFi radio on the router."),
}

# ---------------------------------------------------------------------------
# DIAGNOSTIC CATEGORIES & PRESET TEST SCENARIOS
# ---------------------------------------------------------------------------
CATEGORIES = {
    "network": {
        "title": "Network & Internet Connectivity Issues",
        "description": "Router, Wi-Fi, Ethernet, ISP, DHCP, DNS, and VPN problems.",
        "diagnoses": [
            "router_powered_off", "router_wifi_radio_disabled", "faulty_cable",
            "weak_wifi_signal", "router_hardware_fault", "isp_outage",
            "ip_address_conflict", "dhcp_failure", "dns_failure",
            "vpn_dns_conflict", "proxy_misconfiguration", "firewall_blocking",
            "antivirus_blocking_network"
        ]
    },
    "performance": {
        "title": "System Slowness & Resource Freezing",
        "description": "Malware, thermal throttling, failing drive, background software, low disk space.",
        "diagnoses": [
            "malware_infection", "thermal_throttling", "failing_disk",
            "new_software_resource_conflict", "low_disk_space_slowdown",
            "outdated_driver_performance_issue", "post_update_instability"
        ]
    },
    "crash": {
        "title": "System Crashes & Blue Screens (BSOD)",
        "description": "Kernel driver crashes, hardware thermal tripping, and disk page fault crashes.",
        "diagnoses": [
            "driver_crash", "hardware_overheating_crash", "disk_failure_crash"
        ]
    }
}

PRESETS = [
    {
        "id": "router_off",
        "name": "Router Power Loss",
        "category": "network",
        "description": "No internet access, router power LED is dark.",
        "facts": {"no_internet_access": True, "power_light_on": False},
        "target": "router_powered_off"
    },
    {
        "id": "router_dead",
        "name": "Dead Router (2-Hop)",
        "category": "network",
        "description": "Power on, unpingable gateway even after reboot.",
        "facts": {
            "no_internet_access": True, "power_light_on": True,
            "can_ping_router": False, "router_recently_rebooted": True
        },
        "target": "router_hardware_fault"
    },
    {
        "id": "isp_outage",
        "name": "ISP Service Outage",
        "category": "network",
        "description": "Router reachable, 8.8.8.8 unreachable, all devices down.",
        "facts": {
            "no_internet_access": True, "can_ping_router": True,
            "can_ping_external_ip": False, "multiple_devices_affected": True
        },
        "target": "isp_outage"
    },
    {
        "id": "dns_failure",
        "name": "DNS Resolution Failure (3-Hop)",
        "category": "network",
        "description": "External IP ping works, domain lookup fails, DNS error in browser.",
        "facts": {
            "can_ping_external_ip": True, "can_resolve_dns": False,
            "browser_dns_error_shown": True
        },
        "target": "dns_failure"
    },
    {
        "id": "vpn_conflict",
        "name": "VPN DNS Conflict",
        "category": "network",
        "description": "External IP reachable, DNS broken while corporate VPN is active.",
        "facts": {
            "can_ping_external_ip": True, "can_resolve_dns": False,
            "vpn_active": True
        },
        "target": "vpn_dns_conflict"
    },
    {
        "id": "failing_disk",
        "name": "Failing Hard Drive",
        "category": "performance",
        "description": "System crawling, 100% disk usage, chkdsk shows bad sectors.",
        "facts": {
            "system_slow": True, "high_disk_usage": True, "disk_check_errors": True
        },
        "target": "failing_disk"
    },
    {
        "id": "thermal_throttling",
        "name": "Thermal Throttling",
        "category": "performance",
        "description": "Device overheating, fans at max, high CPU load.",
        "facts": {
            "overheating_detected": True, "high_cpu_usage": True
        },
        "target": "thermal_throttling"
    },
    {
        "id": "malware",
        "name": "Malware Infection",
        "category": "performance",
        "description": "Noticeable system slowdown after malware scan flagged threats.",
        "facts": {
            "system_slow": True, "malware_scan_flagged": True
        },
        "target": "malware_infection"
    },
    {
        "id": "driver_bsod",
        "name": "Driver BSOD Crash",
        "category": "crash",
        "description": "Blue screen crash on machine with outdated device drivers.",
        "facts": {
            "blue_screen_recently": True, "driver_outdated": True
        },
        "target": "driver_crash"
    },
    {
        "id": "mixed_crash_thermal",
        "name": "Overheating BSOD Crash",
        "category": "crash",
        "description": "Blue screen crash occurring when laptop feels burning hot.",
        "facts": {
            "blue_screen_recently": True, "overheating_detected": True
        },
        "target": "hardware_overheating_crash"
    }
]

# ---------------------------------------------------------------------------
# 4. RULES  (28 rules; conditions is a list of fact ids, "!" negates)
# ---------------------------------------------------------------------------
RULES = [
    {"id": "R1", "conditions": ["no_internet_access", "!power_light_on"],
     "conclusion": "router_powered_off",
     "text": "IF no internet access AND router power light is OFF THEN router is powered off."},

    {"id": "R2", "conditions": ["no_internet_access", "power_light_on", "!can_ping_router"],
     "conclusion": "suspect_router_fault",
     "text": "IF no internet access AND router power is ON AND router cannot be pinged THEN suspect router fault."},

    {"id": "R3", "conditions": ["suspect_router_fault", "router_recently_rebooted"],
     "conclusion": "router_hardware_fault",
     "text": "IF router fault is suspected AND the router was already rebooted recently THEN diagnose router hardware fault."},

    {"id": "R4", "conditions": ["no_internet_access", "can_ping_router", "!can_ping_external_ip", "multiple_devices_affected"],
     "conclusion": "isp_outage",
     "text": "IF router is reachable but external IPs are not, AND multiple devices are affected THEN diagnose ISP outage."},

    {"id": "R5", "conditions": ["no_internet_access", "can_ping_router", "!can_ping_external_ip", "!multiple_devices_affected"],
     "conclusion": "suspect_local_config_issue",
     "text": "IF router is reachable but external IPs are not, AND only this device is affected THEN suspect a local configuration issue."},

    {"id": "R6", "conditions": ["suspect_local_config_issue", "ip_conflict_error"],
     "conclusion": "ip_address_conflict",
     "text": "IF a local configuration issue is suspected AND an IP conflict error was shown THEN diagnose IP address conflict."},

    {"id": "R7", "conditions": ["suspect_local_config_issue", "!ip_address_assigned"],
     "conclusion": "dhcp_failure",
     "text": "IF a local configuration issue is suspected AND no valid IP address is assigned THEN diagnose DHCP failure."},

    {"id": "R8", "conditions": ["can_ping_external_ip", "!can_resolve_dns"],
     "conclusion": "suspect_dns_issue",
     "text": "IF external IPs are reachable AND domain names cannot be resolved THEN suspect a DNS issue."},

    {"id": "R9", "conditions": ["suspect_dns_issue", "browser_dns_error_shown"],
     "conclusion": "dns_failure",
     "text": "IF a DNS issue is suspected AND the browser shows a DNS error THEN diagnose DNS resolution failure."},

    {"id": "R10", "conditions": ["suspect_dns_issue", "vpn_active"],
     "conclusion": "vpn_dns_conflict",
     "text": "IF a DNS issue is suspected AND a VPN is active THEN diagnose VPN-caused DNS conflict."},

    {"id": "R11", "conditions": ["no_internet_access", "ethernet_connected", "cable_damage_visible"],
     "conclusion": "faulty_cable",
     "text": "IF no internet access over Ethernet AND the cable shows visible damage THEN diagnose faulty cable."},

    {"id": "R12", "conditions": ["no_internet_access", "wifi_connected", "signal_strength_weak"],
     "conclusion": "weak_wifi_signal",
     "text": "IF no internet access over WiFi AND signal strength is weak THEN diagnose weak WiFi signal."},

    {"id": "R13", "conditions": ["no_internet_access", "proxy_configured", "!can_ping_external_ip"],
     "conclusion": "proxy_misconfiguration",
     "text": "IF no internet access AND a proxy is configured AND external IPs are unreachable THEN diagnose proxy misconfiguration."},

    {"id": "R14", "conditions": ["no_internet_access", "firewall_recently_changed"],
     "conclusion": "firewall_blocking",
     "text": "IF no internet access AND firewall settings were changed recently THEN diagnose firewall blocking traffic."},

    {"id": "R15", "conditions": ["no_internet_access", "antivirus_blocking_notification"],
     "conclusion": "antivirus_blocking_network",
     "text": "IF no internet access AND antivirus raised a blocking notification THEN diagnose antivirus blocking network."},

    {"id": "R16", "conditions": ["system_slow", "high_cpu_usage", "!malware_scan_flagged"],
     "conclusion": "suspect_resource_heavy_process",
     "text": "IF system is slow AND CPU usage is high AND no malware was flagged THEN suspect a resource-heavy process."},

    {"id": "R17", "conditions": ["suspect_resource_heavy_process", "new_software_installed"],
     "conclusion": "new_software_resource_conflict",
     "text": "IF a resource-heavy process is suspected AND new software was just installed THEN diagnose resource conflict from new software."},

    {"id": "R18", "conditions": ["system_slow", "malware_scan_flagged"],
     "conclusion": "malware_infection",
     "text": "IF system is slow AND a malware scan flagged threats THEN diagnose possible malware infection."},

    {"id": "R19", "conditions": ["system_slow", "low_disk_space"],
     "conclusion": "low_disk_space_slowdown",
     "text": "IF system is slow AND free disk space is below 10% THEN diagnose slowdown due to low disk space."},

    {"id": "R20", "conditions": ["system_slow", "high_disk_usage", "disk_check_errors"],
     "conclusion": "failing_disk",
     "text": "IF system is slow AND disk usage is high AND a disk check shows errors THEN diagnose a failing disk."},

    {"id": "R21", "conditions": ["system_slow", "driver_outdated"],
     "conclusion": "outdated_driver_performance_issue",
     "text": "IF system is slow AND drivers are outdated THEN diagnose outdated driver performance issue."},

    {"id": "R22", "conditions": ["system_slow", "os_recently_updated", "!malware_scan_flagged", "!low_disk_space"],
     "conclusion": "post_update_instability",
     "text": "IF system is slow shortly after an OS update, with no malware and disk space is fine THEN diagnose post-update instability."},

    {"id": "R23", "conditions": ["overheating_detected", "high_cpu_usage"],
     "conclusion": "thermal_throttling",
     "text": "IF the device is overheating AND CPU usage is high THEN diagnose thermal throttling."},

    {"id": "R24", "conditions": ["blue_screen_recently", "driver_outdated"],
     "conclusion": "driver_crash",
     "text": "IF a recent crash occurred AND drivers are outdated THEN diagnose a driver-caused crash."},

    {"id": "R25", "conditions": ["blue_screen_recently", "overheating_detected"],
     "conclusion": "hardware_overheating_crash",
     "text": "IF a recent crash occurred AND the device is overheating THEN diagnose an overheating-caused crash."},

    {"id": "R26", "conditions": ["blue_screen_recently", "disk_check_errors"],
     "conclusion": "disk_failure_crash",
     "text": "IF a recent crash occurred AND disk check shows errors THEN diagnose a disk-failure-caused crash."},

    {"id": "R27", "conditions": ["no_internet_access", "wifi_connected", "!wifi_light_on"],
     "conclusion": "router_wifi_radio_disabled",
     "text": "IF no internet access over WiFi AND the router's WiFi light is off THEN diagnose router WiFi radio disabled."},

    {"id": "R28", "conditions": ["no_internet_access", "power_light_on", "can_ping_router", "can_ping_external_ip", "can_resolve_dns"],
     "conclusion": "suspect_local_config_issue",
     "text": "IF everything up to DNS resolution tests fine but internet access is still reported as failing THEN suspect an application-level/local configuration issue (browser, host file, etc.)."},
]

# ---------------------------------------------------------------------------
# 5. RULE PROVENANCE
# ---------------------------------------------------------------------------
# Per the assignment's requirement that rules must not be authored from
# scratch (or generated by an LLM) but must be traceable to a real source,
# every rule above maps to one of the cited references below. Full citation
# text with URLs is given in the submitted report's References section and
# Annex; this dict exists so the code itself documents provenance, not just
# the paperwork.
RULE_PROVENANCE = {
    "R1": {
        "title": "Microsoft Support: Fix Ethernet connection problems in Windows / Fix Wi-Fi connection issues in Windows",
        "url": "https://support.microsoft.com/en-us/windows/fix-wi-fi-connection-issues-in-windows-9b725c49-60cc-f138-8556-5d5d1136da0d",
        "source": "Official Microsoft Knowledge Base (Restart modem/router steps)"
    },
    "R2": {
        "title": "Microsoft Support: Fix Wi-Fi connection issues in Windows",
        "url": "https://support.microsoft.com/en-us/windows/fix-wi-fi-connection-issues-in-windows-9b725c49-60cc-f138-8556-5d5d1136da0d",
        "source": "Official Microsoft Windows Network Diagnostics (Ping default gateway/router)"
    },
    "R3": {
        "title": "Microsoft Support: Fix Wi-Fi connection issues in Windows",
        "url": "https://support.microsoft.com/en-us/windows/fix-wi-fi-connection-issues-in-windows-9b725c49-60cc-f138-8556-5d5d1136da0d",
        "source": "Official Microsoft Windows Network Diagnostics (Ping test failing persistently after power-cycle)"
    },
    "R4": {
        "title": "Microsoft Support: Fix Wi-Fi connection issues in Windows",
        "url": "https://support.microsoft.com/en-us/windows/fix-wi-fi-connection-issues-in-windows-9b725c49-60cc-f138-8556-5d5d1136da0d",
        "source": "Official Microsoft Support (External IP ping failure across multiple LAN clients isolating ISP outage)"
    },
    "R5": {
        "title": "Microsoft Support: Fix Wi-Fi connection issues in Windows",
        "url": "https://support.microsoft.com/en-us/windows/fix-wi-fi-connection-issues-in-windows-9b725c49-60cc-f138-8556-5d5d1136da0d",
        "source": "Official Microsoft Support (Single-device isolation indicating local client configuration fault)"
    },
    "R6": {
        "title": "Microsoft Learn: Fix duplicate IP address conflicts on a DHCP network",
        "url": "https://learn.microsoft.com/en-us/troubleshoot/windows-server/networking/duplicate-ip-address-conflicts-on-dhcp",
        "source": "Microsoft Learn Networking Technical Documentation (Duplicate IP detection)"
    },
    "R7": {
        "title": "Microsoft Learn: Troubleshoot DHCP client issues (APIPA / No DHCP lease)",
        "url": "https://learn.microsoft.com/en-us/troubleshoot/windows-server/networking/troubleshoot-dhcp-client-issues",
        "source": "Microsoft Learn Technical Documentation (APIPA 169.254.x.x DHCP exhaustion/failure)"
    },
    "R8": {
        "title": "Google Public DNS Documentation: Troubleshooting DNS Resolution",
        "url": "https://developers.google.com/speed/public-dns/docs/troubleshooting",
        "source": "Google Developers Public DNS Documentation (External IP ping succeeds but DNS lookups fail)"
    },
    "R9": {
        "title": "Google Public DNS Documentation: Troubleshooting Public DNS & Browser DNS Errors",
        "url": "https://developers.google.com/speed/public-dns/docs/troubleshooting",
        "source": "Google Developers Public DNS Documentation (DNS_PROBE_FINISHED_NXDOMAIN verification)"
    },
    "R10": {
        "title": "Microsoft GitHub / WSL Documentation: VPN DNS resolution routing conflict (Issue #8022)",
        "url": "https://github.com/microsoft/WSL/issues/8022",
        "source": "Microsoft Technical Community Documentation (Active tunnel overriding DNS adapter metric)"
    },
    "R11": {
        "title": "Microsoft Support: Fix Ethernet connection problems in Windows",
        "url": "https://support.microsoft.com/en-us/windows/fix-ethernet-connection-problems-in-windows-231a080b-66ef-14e2-cd46-b570d27f5a0d",
        "source": "Microsoft Support (Physical Ethernet cable inspection and link state)"
    },
    "R12": {
        "title": "Microsoft Support: Fix Wi-Fi connection issues in Windows (Weak Wireless Signal)",
        "url": "https://support.microsoft.com/en-us/windows/fix-wi-fi-connection-issues-in-windows-9b725c49-60cc-f138-8556-5d5d1136da0d",
        "source": "Microsoft Support (Signal strength attenuation & distance troubleshooting)"
    },
    "R13": {
        "title": "Microsoft Learn: Troubleshoot proxy server connectivity in Windows",
        "url": "https://learn.microsoft.com/en-us/troubleshoot/windows-server/networking/troubleshoot-proxy-server-connectivity",
        "source": "Microsoft Learn Troubleshooting Guide (Proxy server misconfiguration blocking WAN routing)"
    },
    "R14": {
        "title": "Microsoft Learn: Diagnosing Windows Defender Firewall problems",
        "url": "https://learn.microsoft.com/en-us/windows/security/operating-system-security/network-security/windows-firewall/diagnose-problems",
        "source": "Microsoft Security Documentation (Recent rule change blocking outbound packet flow)"
    },
    "R15": {
        "title": "Microsoft Learn: Troubleshoot network protection / security suite blocking",
        "url": "https://learn.microsoft.com/en-us/microsoft-365/security/defender-endpoint/troubleshoot-network-protection",
        "source": "Microsoft Defender Documentation (Antivirus/EDR network filter blocking alerts)"
    },
    "R16": {
        "title": "Microsoft Support: Tips to improve PC performance in Windows",
        "url": "https://support.microsoft.com/en-us/windows/tips-to-improve-pc-performance-in-windows-b3b3ef4b-5953-67cb-667e-4f5ca86cf140",
        "source": "Official Microsoft Windows Performance Guide (Task Manager high CPU isolation)"
    },
    "R17": {
        "title": "Microsoft Support: Tips to improve PC performance in Windows (Software conflict)",
        "url": "https://support.microsoft.com/en-us/windows/tips-to-improve-pc-performance-in-windows-b3b3ef4b-5953-67cb-667e-4f5ca86cf140",
        "source": "Microsoft Performance Guide (Newly installed software background resource drain)"
    },
    "R18": {
        "title": "Microsoft Support: Stay protected with Windows Security",
        "url": "https://support.microsoft.com/en-us/windows/stay-protected-with-windows-security-2ae0363d-0aa8-47ac-4698-50495cbaf8f0",
        "source": "Microsoft Windows Security Documentation (Malware scan detection & performance impact)"
    },
    "R19": {
        "title": "Microsoft Support: Free up drive space in Windows",
        "url": "https://support.microsoft.com/en-us/windows/free-up-drive-space-in-windows-a180e030-e182-7a66-b771-5c85d5f7a972",
        "source": "Official Microsoft Storage Guide (System degradation under low free disk space < 10%)"
    },
    "R20": {
        "title": "Microsoft Learn: chkdsk command reference & troubleshooting disk errors",
        "url": "https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/chkdsk",
        "source": "Microsoft System Administration Reference (Sustained 100% disk I/O combined with SMART/chkdsk bad sectors)"
    },
    "R21": {
        "title": "Microsoft Support: Update drivers manually in Windows",
        "url": "https://support.microsoft.com/en-us/windows/update-drivers-manually-in-windows-ec62f46c-ff14-c91d-eead-d7126dc1f7b6",
        "source": "Microsoft Windows Driver Management Documentation (Outdated hardware drivers causing DPC latency)"
    },
    "R22": {
        "title": "Microsoft Support: How to uninstall a Windows Update",
        "url": "https://support.microsoft.com/en-us/windows/how-to-uninstall-a-windows-update-c77b8f9b-e4dc-4e9f-a803-f1e2e398ad3e",
        "source": "Microsoft Support (OS patch regression & post-update file re-indexing)"
    },
    "R23": {
        "title": "Dell Technical Support: How to Troubleshoot Overheating, Shutdown, or Thermal Throttling",
        "url": "https://www.dell.com/support/kbdoc/en-us/000130889/how-to-troubleshoot-a-overheating-shutdown-or-thermal-issue-on-a-dell-pc",
        "source": "Dell Hardware Engineering Knowledge Base (High CPU temperature triggering PROCHOT thermal clock throttling)"
    },
    "R24": {
        "title": "Microsoft Support: Resolving Blue Screen (BSOD) errors in Windows",
        "url": "https://support.microsoft.com/en-us/windows/resolving-blue-screen-errors-in-windows-60844283-380e-c6da-2f48-d4e82aa9e84c",
        "source": "Microsoft Windows Kernel Crash Documentation (Outdated or incompatible third-party kernel driver crash)"
    },
    "R25": {
        "title": "Dell Technical Support: Blue Screen (BSOD) Errors and Stop Code Issues",
        "url": "https://www.dell.com/support/kbdoc/en-us/000124340/how-to-troubleshoot-blue-screen-or-stop-error-code-on-a-dell-computer",
        "source": "Dell Support Knowledge Base (Thermal shutdown & thermal trip bugchecks: WHEA_UNCORRECTABLE_ERROR)"
    },
    "R26": {
        "title": "Microsoft Learn: Bug Check 0x77 & 0x7A: KERNEL_DATA_INPAGE_ERROR",
        "url": "https://learn.microsoft.com/en-us/windows-hardware/drivers/debugger/bug-check-0x7a--kernel-data-inpage-error",
        "source": "Microsoft Windows Debugging Documentation (Disk read failure / I/O CRC error causing kernel paging crash)"
    },
    "R27": {
        "title": "Microsoft Support: Fix Wi-Fi connection issues in Windows (Physical / Software Radio Switch)",
        "url": "https://support.microsoft.com/en-us/windows/fix-wi-fi-connection-issues-in-windows-9b725c49-60cc-f138-8556-5d5d1136da0d",
        "source": "Microsoft Support (Router 802.11 RF radio broadcast turned off / disabled via schedule)"
    },
    "R28": {
        "title": "Microsoft Support: Fix Wi-Fi connection issues in Windows (Network Reset & Winsock Stack)",
        "url": "https://support.microsoft.com/en-us/windows/fix-wi-fi-connection-issues-in-windows-9b725c49-60cc-f138-8556-5d5d1136da0d",
        "source": "Microsoft Support (L1-L3 network stacks verify clean, isolating local L7 software proxy/socket corruption)"
    }
}

SOURCES = {rid: f"{data['title']} - {data['url']}" for rid, data in RULE_PROVENANCE.items()}

ALL_FACT_LABELS = {}
ALL_FACT_LABELS.update(FACTS)
ALL_FACT_LABELS.update(INTERMEDIATE_LABELS)
ALL_FACT_LABELS.update({k: v[0] for k, v in DIAGNOSES.items()})


def label(fact_id: str) -> str:
    """Human-readable label for any fact id (askable, intermediate, or diagnosis)."""
    return ALL_FACT_LABELS.get(fact_id, fact_id)


def validate_kb():
    """Static integrity check: every rule's fact ids must be declared somewhere.
    Returns a list of problems (empty list = KB is internally consistent)."""
    problems = []
    known = set(FACTS) | set(INTERMEDIATE_LABELS) | set(DIAGNOSES)
    for rule in RULES:
        for cond in rule["conditions"]:
            fact = cond[1:] if cond.startswith("!") else cond
            if fact not in known:
                problems.append(f"{rule['id']}: unknown condition fact '{fact}'")
        if rule["conclusion"] not in known:
            problems.append(f"{rule['id']}: unknown conclusion fact '{rule['conclusion']}'")
    for d in DIAGNOSES:
        if not any(r["conclusion"] == d for r in RULES):
            problems.append(f"Diagnosis '{d}' is never concluded by any rule")
    return problems


if __name__ == "__main__":
    issues = validate_kb()
    print(f"Facts: {len(FACTS)} askable + {len(INTERMEDIATE_LABELS)} intermediate + {len(DIAGNOSES)} diagnoses")
    print(f"Rules: {len(RULES)}")
    print("KB OK" if not issues else "KB ISSUES:\n" + "\n".join(issues))
