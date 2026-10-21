---
layout: post
title: "Create the Foundation, Part 3: Memory Protection — Turning the Map into an Enforced Boundary"
date: 2026-09-04
categories: [System & SW Architecture]
tags: [architecture, project-foundation, memory-protection, mpu, dma, freedom-from-interference, autosar, asil, cortex-m7]
premium_slug: create-the-foundation-part-3-protection-allocation-and-cpu-load
---

*This is Part 3 of a series on laying the foundation for a new ECU project. [Part 1]({% post_url 2026-08-30-create-the-foundation-part-1-requirements-and-thinking %}) covered requirements research and the thinking process; [Part 2]({% post_url 2026-09-03-create-the-foundation-part-2-memory-mapping-and-partitioning %}) covered memory mapping and partitioning; this part covers memory protection — MPU, bus masters and peripherals; [Part 4]({% post_url 2026-10-19-create-the-foundation-part-4-swc-allocation-and-task-setup %}) covers SWC allocation, a first CPU budget and a first task setup.*

In [Part 2]({% post_url 2026-09-03-create-the-foundation-part-2-memory-mapping-and-partitioning %}), we drew a memory map for our ASIL B BCU on our ARM Cortex-M7-based automotive MCU: flash split by criticality and update strategy, RAM split across one simplex ASIL B core and five independent QM cores, plus a standby region and a shared region for the things that genuinely need to cross the boundary. A memory map on its own is a diagram. What turns it into something you can actually put your safety case behind is three more decisions: how it's enforced, whether the hardware can actually carry the load we're about to put on it, and what runs where. This part covers the first one, and it's big enough to deserve a part of its own. What runs where, and whether the hardware can carry it, follow in [Part 4]({% post_url 2026-10-19-create-the-foundation-part-4-swc-allocation-and-task-setup %}).

## What's inside

- Who may execute whose code, and who may read and write whose data, as access matrices per core
- A worked example, ASIL B flash vs. the shared SRAM block, down to the MPU registers
- Why you run out of MPU regions faster than you expect, and the AUTOSAR version of the same problem
- Two experiments on an RTOS MPU port
- The doors the MPU doesn't guard: DMA, other bus masters and peripherals

{% include premium-unlock.html %}
