---
layout: post
title: "Create the Foundation, Part 2: Memory Mapping and Partitioning"
date: 2026-09-03
categories: [System & SW Architecture]
tags: [architecture, project-foundation, memory-mapping, partitioning, flash-memory, autosar, asil, cortex-m7]
premium_slug: create-the-foundation-part-2-memory-mapping-and-partitioning
---

*This is Part 2 of a series on laying the foundation for a new ECU project. [Part 1]({% post_url 2026-08-30-create-the-foundation-part-1-requirements-and-thinking %}) covered requirements research and the thinking process; this part covers memory mapping and partitioning; [Part 3]({% post_url 2026-09-04-create-the-foundation-part-3-protection-allocation-and-cpu-load %}) covers memory protection — MPU, bus masters and peripherals; [Part 4]({% post_url 2026-10-19-create-the-foundation-part-4-swc-allocation-and-task-setup %}) covers SWC allocation, a first CPU budget and a first task setup.*

In [Part 1]({% post_url 2026-08-30-create-the-foundation-part-1-requirements-and-thinking %}), we picked our microcontroller: an ARM Cortex-M7-based automotive MCU, six cores at around 300 MHz, configured for our ASIL B project as one simplex ASIL B core plus five independent QM cores — instead of burning a core on lockstep redundancy we don't need. We also gathered security (a root of trust), updateability (independently updatable blocks), communication (a ComStack reachable from multiple components), diagnostics (somewhere persistent to live), low power and startup time (an always-on ECU that has to talk early), and the rules of our memory protection hardware (8 or 16 MPU regions per core, each one a power of two, aligned to its own size) as requirements. None of that is a memory map yet. This is where we turn it into one.

## What's inside

- How the flash gets split: immutable blocks first, then the updatable ones, with OTP, bootloaders, HSM partitions and reserved blocks that only exist so the MPU can do its job
- The full address-based flash map with sector sizes, generated from a YAML file that a script checks before it draws anything
- RAM for one simplex ASIL B core and five QM cores, plus the memory that has to survive a reset
- Where security, diagnostics, communication and startup time from Part 1 ended up in the map
- The requirements nobody writes down, and what's still open for the next parts

{% include premium-unlock.html %}
