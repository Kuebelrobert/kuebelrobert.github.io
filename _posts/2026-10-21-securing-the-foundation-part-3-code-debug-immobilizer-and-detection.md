---
layout: post
title: "Securing the Foundation, Part 3: Code, Debug, Immobilizer and Detection"
date: 2026-10-21
categories: [Security]
tags: [security, secure-coding, fuzzing, sbom, debug-protection, lifecycle, immobilizer, ids, privacy, iso-21434, cortex-m7]
premium_slug: securing-the-foundation-part-3-code-debug-immobilizer-and-detection
---

*This is Part 3 of a three-part series on embedded security for our BCU. [Part 1]({% post_url 2026-10-21-securing-the-foundation-part-1-threat-model-root-of-trust-and-boot %}) covers the threat model, the root of trust and the boot concept; [Part 2]({% post_url 2026-10-21-securing-the-foundation-part-2-updates-bus-and-diagnostics %}) covers updates, the bus and diagnostics; this part covers the code, the debug port, the immobilizer, detection and privacy. The example is the BCU from the [foundation series]({% post_url 2026-10-19-create-the-foundation-part-4-swc-allocation-and-task-setup %}).*

[Part 1]({% post_url 2026-10-21-securing-the-foundation-part-1-threat-model-root-of-trust-and-boot %}) built the base: TARA, HSM, keys and boot. [Part 2]({% post_url 2026-10-21-securing-the-foundation-part-2-updates-bus-and-diagnostics %}) put locks on the three doors that are open by design: updates, the bus and diagnostics. This last part is about the doors that are easy to forget: the code behind all those locks, the debug port, the immobilizer (where security isn't a protection, it's the function), noticing an attack, and the data the BCU collects without anybody asking. At the end, everything comes together in one table: which security mechanism lives where in the BCU, and what it costs.

## What's inside

- Door 6, the code itself: parsers, pointers and other gifts
- Door 7, the debug port and the ECU lifecycle
- Door 8, the immobilizer: security as the actual function
- Door 9, detection and response, and Door 10, privacy
- Where security lives in the BCU: one table for every mechanism, and the process around it

{% include premium-unlock.html %}
