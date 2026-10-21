---
layout: post
title: "Securing the Foundation, Part 2: Updates, the Bus and Diagnostics"
date: 2026-10-21
categories: [Security]
tags: [security, secure-update, anti-rollback, post-quantum, secoc, can-fd, lin, gateway, uds, cortex-m7]
premium_slug: securing-the-foundation-part-2-updates-bus-and-diagnostics
---

*This is Part 2 of a three-part series on embedded security for our BCU. [Part 1]({% post_url 2026-10-21-securing-the-foundation-part-1-threat-model-root-of-trust-and-boot %}) covers the threat model, the root of trust and the boot concept; this part covers updates, the bus and diagnostics; [Part 3]({% post_url 2026-10-21-securing-the-foundation-part-3-code-debug-immobilizer-and-detection %}) covers the code, the debug port, the immobilizer, detection and privacy. The example is the BCU from the [foundation series]({% post_url 2026-10-19-create-the-foundation-part-4-swc-allocation-and-task-setup %}).*

In [Part 1]({% post_url 2026-10-21-securing-the-foundation-part-1-threat-model-root-of-trust-and-boot %}), we built the base: a TARA for the BCU, an HSM that keeps every key behind its firewall, a key inventory, and a boot concept that fits into the 150 ms startup budget because the keys, not the start, depend on the verification. If you skipped it, at least look at the attack surface map there. This part uses its door numbers.

This part covers the three doors that are open while the ECU is running, by design: the update path, which is *supposed* to put new code into the ECU; the bus, where every ECU is supposed to talk; and diagnostics, which is supposed to give a tester control over the ECU. The question isn't how to close them. It's how to make sure only the right people get through.

## What's inside

- Door 3, updates: check before you erase, anti-rollback, and the problem with "immutable"
- Door 4, the bus: SecOC on CAN FD, the brake light with security, LIN, Ethernet and the gateway
- Door 5, diagnostics: the door with a key under the mat

{% include premium-unlock.html %}
