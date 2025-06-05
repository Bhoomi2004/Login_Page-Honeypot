# 🔐 Honeypot Project: Login System for Cyber Threat Detection

The **Honeypot Project** is a cybersecurity tool designed to **capture, analyze, and mitigate unauthorized login attempts** by simulating a fake login page. Acting as a decoy, this honeypot login system attracts potential attackers and records their behavior, providing valuable insights into attack patterns and threat sources.

## 🚀 Project Overview

This project creates a realistic **fake login interface** that entices malicious actors to enter credentials, unaware that their actions are being monitored. All login attempts are meticulously logged in a **PostgreSQL database**, including:

* Timestamp of the attempt
* Entered username and password
* IP address and geolocation data
* User-agent information

The system uses multiple layers of security analysis:

* **Suspicious IP Detection:** Monitors IP addresses for repeated or unusual access patterns to identify potential attackers.
* **Breached Credentials Verification:** Checks submitted credentials against known compromised databases to detect attempts using leaked or stolen passwords.
* **Automatic Threat Blocking:** Implements rules to block IPs exhibiting malicious behavior, preventing repeated intrusion attempts.

To enhance visibility and proactive defense, the captured data is visualized through **Power BI dashboards** that display real-time analytics of attack frequency, source locations, and credential trends.

## 🎯 Purpose and Impact

* **Cybersecurity Awareness:** Educates organizations and individuals about common attack vectors targeting login pages.
* **Threat Intelligence:** Collects actionable data to understand attacker behavior and improve defense strategies.
* **Research and Development:** Provides a practical platform for testing and enhancing intrusion detection methods.

## ⚙️ Technologies Used

* Backend: Python (for logging, analysis, and threat detection)
* Database: SupaBase (for secure and structured data storage)
* Visualization: Power BI (for dynamic and interactive attack pattern dashboards)
