---
trigger: always_on
description: Never expose cloud infrastructure, deployment architecture, or port numbers in customer-facing UI, and avoid all AI/vibecoded UI clichés.
---

# Customer-Facing UI & Security Rules (Permanent)

1. **Zero Infrastructure or Deployment Leaks in UI:**
   - NEVER display cloud provider names (`AWS`, `Azure`, `GCP`), services (`Lambda`, `DynamoDB`, `Kinesis`, `EC2`, `S3`, `API Gateway`), regions (`eu-north-1`, `us-east-1`, `Stockholm`), runtimes (`Python 3.12`), or port numbers (`8081`, `8080`, `localhost`) anywhere in customer-facing HTML, UI labels, footers, tooltips, Terms of Service, or Privacy Policies.
   - NEVER label UI sections with internal homework/spec numbers like `Feature 1`, `Feature 2`, `Feature 5`, `Feature 7`, or `MOCK_DEMO_DATA` in visible customer copy. Use natural product terminology (e.g., *Network & Origin*, *Account Activity*, *Location & Velocity*, *Customer Profile*, *Case Resolution*).

2. **Natural, Human-Crafted Product Design (Zero "Vibecoded" Tells):**
   - No harsh gradients, neon glows, purple-and-black themes, radial orbs, dot grids, or glassmorphism.
   - No pseudo-terminal AI clichés either: NO `01 //`, `//` double-slash prefixes, NO `[BRACKETED]` button text (`[CLOSE]`, `[ESC]`), NO shouting ALL-CAPS paragraphs, and NO em-dashes (`—`) or emojis.
   - Use natural sentence case for headings, buttons, and labels (like Stripe Radar, Mercury, or Ramp), balanced whitespace, subtle `6px` human-standard border radii on controls, clean `1px` neutral borders, and refined typography.
