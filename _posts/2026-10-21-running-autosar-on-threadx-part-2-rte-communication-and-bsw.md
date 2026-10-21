---
layout: post
title: "Running an AUTOSAR Project on ThreadX, Part 2: RTE Communication and Basic Software"
date: 2026-10-21
categories: [System & SW Architecture]
tags: [architecture, autosar, rte, threadx, rtos, migration, asil]
premium_slug: running-autosar-on-threadx-part-2-rte-communication-and-bsw
---

*This is Part 2 of a two-part post on running AUTOSAR components on ThreadX. [Part 1]({% post_url 2026-10-20-running-autosar-on-threadx-part-1-os-and-execution-model %}) covered the OS side: runnables and RTE events, tasks, resources, alarms, interrupts and multicore. This part covers RTE communication, basic software, and the bill at the end.*

Quick recap of the idea from Part 1: the components stay exactly as they are, including every `Rte_Read` and `Rte_Call`. The generated RTE API headers stay the contract; underneath, a generated shim fulfills that contract with ThreadX primitives. Every mechanism gets a rating:

- **Native** — ThreadX has a primitive that does the job.
- **Shim** — a thin layer of your code on top of ThreadX primitives.
- **Build** — ThreadX has nothing close. You design and implement it, and for safety-relevant parts, you also argue it.

In Part 1, we gave every OS task a thread and a dispatcher loop that wakes up on event flags. Now we fill in what the runnables actually do through their ports. The example project is still the BCU from the [foundation series]({% post_url 2026-10-19-create-the-foundation-part-4-swc-allocation-and-task-setup %}): six Cortex-M7 cores, one ASIL B core, five QM cores.

## What's inside

- Sender-receiver communication, unqueued and queued, on ThreadX primitives
- Implicit vs. explicit communication: when a runnable gets a snapshot and when it sees the writer's new value
- Client-server, synchronous and asynchronous, and mode management
- Basic software on ThreadX
- The summary table: native, shim or build for every mechanism, and what you lose (and how to win some of it back)

{% include premium-unlock.html %}
