---
layout: post
title: "Garbage Collection - friend or enemy"
date: 2026-08-29
categories: [Flashing]
tags: [garbage-collection, flash-memory, wear-leveling, nvm, firmware-update]
---

<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>mermaid.initialize({ startOnLoad: true, theme: "dark" });</script>

Garbage collection or in short GC is a mechanism that takes care of "cleaning up" old, invalidated flash data so new data can be written. Before garbage collection can step into action, I need to explain why we need this clean-up at all.

A car stores values like operating-hour counters, mileage, or calibration offsets for sensors inside its data flash. Over the lifecycle of the car, these values change from time to time — due to firmware updates or the recalibration of sensor data. They are typically required to be non-volatile, meaning they need to survive the ECU going into a power-down.

RAM cells normally lose their content once power is removed, while flash is able to retain it even after the whole microcontroller is without supply. There are several types of non-volatile memory, but I'll focus on NOR flash here, since it's the type most commonly built directly into automotive microcontrollers — as opposed to NAND flash, which you'll more commonly find in mass-storage devices like SD cards or SSDs.

To change a value in flash, you can't just overwrite it: you always have to erase the content first and then write the actual value. Erasing happens at the granularity of a whole sector, not a single byte, and it's this erase-before-write property that causes most of the fun described below.

Repeated erase/write cycles wear a flash cell out over time — every cell has a limited number of program/erase cycles it can survive (its *endurance*) before it becomes unreliable, which in turn affects how long it can still reliably hold data (its *data retention*). To keep this wear evenly distributed across the memory, software needs to make sure each cell is written roughly the same number of times. This is called wear leveling, and it's typically done by not always overwriting the same cell but instead writing consecutively into the next available cells.

Since this strategy leaves behind a trail of stale, invalidated data every time it writes to a new cell, someone eventually needs to clean up that mess. That someone is garbage collection: it waits until the amount of garbage reaches a certain threshold, and then reclaims space by copying the still-valid content into a new, clean sector before erasing the old one.

<div class="mermaid">
flowchart LR
    subgraph Before["1. Before GC"]
        direction TB
        A1["Sector A (active)<br/>Valid + invalid data mixed"]
        A2["Sector B (clean)<br/>Empty, standby"]
    end
    subgraph During["2. During GC"]
        direction TB
        B1["Sector A (active)<br/>Still readable, not yet erased"]
        B2["Sector B (filling)<br/>Valid entries copied over"]
    end
    subgraph After["3. After GC"]
        direction TB
        C1["Sector A (erased)<br/>New clean standby"]
        C2["Sector B (active)<br/>Only valid data remains"]
    end
    Before --> During --> After
</div>

*Figure 1: A garbage collection pass doesn't clean a sector in place — it copies the still-valid data into the clean standby sector, flips which sector is "active," and only then erases the old one.*

And just like cleaning up your own room, garbage collection takes time — and needs to be scheduled with some sense of priority. You also really don't want to get interrupted in the middle of that cleaning process, since an interruption during an erase can leave you with neither a valid old copy nor a complete new one.

Now we know the why, and so far it sounds like a pretty favorable service. So where's the problem?

Updating software is a crucial part of cars and their ECUs — the same goes for IoT devices, mobile phones, and so on. The problem can occur when you're in the middle of a flashing sequence and you hit the garbage collection threshold at the same time.

Do you want to wait until garbage collection is finished? Is your system stable enough to deal with that? And aren't you violating some timing requirement by waiting on garbage collection in the first place?

Now here is where good architecture needs to earn its paycheck.

## A concrete example

Imagine an application that's split into independently updatable blocks — say, one block that's purely code (functions and constants), and another that holds only the calibration data for those functions. The overall system consists of a boot manager, a flash bootloader, and the application itself. A typical flashing sequence then looks like this:

1. The boot manager notices a pending flash request.
2. It jumps into the flash bootloader.
3. The flash bootloader flashes the application block by block.
4. After each block, it writes a progress marker into NVM — so that if a supply glitch causes a reset mid-sequence, the system knows exactly where it left off instead of guessing.

<div class="mermaid">
sequenceDiagram
    participant BM as Boot Manager
    participant BL as Flash Bootloader
    participant APP as Application Blocks
    participant NVM as NVM / Flash

    BM->>BM: Detect pending flash request
    BM->>BL: Jump to Flash Bootloader
    loop For each application block
        BL->>APP: Flash block
        BL->>NVM: Write progress marker
        NVM-->>BL: GC trigger? (maybe)
    end
    BL->>BM: Flashing complete, jump back
</div>

*Figure 2: Every block write ends with a progress marker in NVM — and every one of those writes is a place where garbage collection can decide to join the party.*

Every single actor in that chain — boot manager, bootloader, application — can write to NVM, and every one of those writes is a potential GC trigger. Which means the one operation you added specifically to make flashing *safer* (the progress marker) is also the one most likely to invite the process that can make flashing *slower*, right when you can least afford it.

## What you can actually do about it

"Just suppress GC during flashing" is the answer everybody reaches for first, and it's not wrong — but it's not free either. If you defer every GC trigger for the full duration of a flash sequence, the garbage keeps piling up right up until the moment you release the brakes again. Do that often enough, or make your flash sequence long enough, and you can walk straight into the situation GC was invented to prevent: no clean sector left to write into.

A pattern that works better in practice is to give GC a *budget* instead of a blanket ban. Between block writes — at defined, predictable points in the flash sequence — check how full your garbage backlog is. If you're comfortably below your threshold, defer and keep flashing. If you're getting close to running out of clean sectors, spend a bounded amount of time letting GC catch up right there, before it becomes an emergency. That way GC still runs during flashing, just on your terms and inside a time slot you've already accounted for in your timing budget — instead of showing up uninvited in the middle of the block you least expected.

Whatever strategy you pick, don't rely on the happy path holding up in the field. Always keep timeouts and fail-safe mechanisms in place, so that even if GC is allowed to run during flashing and the flashing itself fails, you can still fall back to a safe, previously validated backup image.

## The decision, written down properly

Everything above is the reasoning. If you'd rather hand the actual decision to a coding agent instead of re-deriving it from paragraphs — or just want something you can skim in thirty seconds instead of read — I've written it up as a compact Architecture Decision Record: [`ADR-0001: Budget garbage collection during flash sequences`](https://github.com/Kuebelrobert/sw_arch_blog/blob/main/_adr/0001-gc-budget-during-flash-sequences.md). It also answers a question that comes up the moment you're building this inside a platform instead of a single product: does GC budgeting even belong at the platform level, or is it product-specific plumbing? (Short version: platform — every derivative on the same NVM/FEE stack hits the identical problem, and nothing about the fix is product business logic.) The ADR stays short on purpose — a decision flowchart plus one fenced, structured block (interface, tunables, acceptance criteria) that an AI coding agent can work from directly, instead of paragraphs it would have to reverse-engineer first. Notice what it still doesn't do: hand you a specific threshold percentage or budget-in-milliseconds as if I'd already decided it for you. Those stay `calibration_required: true` — they depend on your sector size, your GC cost, and your actual target.


## Weak spots to check in your own architecture

If you're starting a project, these are the questions worth answering before GC and flashing collide on you for real, and not on a whiteboard:

- Timing budget: can you afford a GC run happening during flashing at all, or does it blow your update time budget?
- Field vs. production: field devices need to survive a worst case gracefully, but don't forget production — the line wants deterministic, repeatable flash timing just as much, if not more.
- Suppression: can you actually suppress garbage collection during flashing, and if so, for how long before the backlog becomes a problem?
- Fallback: do you have timeouts and fail-safe mechanisms so that a failed flash — with or without GC involved — still leaves you on a validated backup image, not a brick?
- Lifecycle: have you planned GC handling early enough to cover different target versions, especially the ones that may no longer be field-updatable after they've shipped?

There are many more things to consider, but I hope this gives you some awareness of the dangers — and the potential — of designing your system around the health of your data flash, so you can be bulletproof the day GC decides it wants to compete with your delivery date.


## Sources and further reading

### Specifications

- [AUTOSAR Classic Platform: Specification of Flash EEPROM Emulation (Fee), R23-11](https://www.autosar.org/fileadmin/standards/R23-11/CP/AUTOSAR_CP_SWS_FlashEEPROMEmulation.pdf) — the module that owns garbage collection in an AUTOSAR stack, and where the "when is GC allowed to run" question officially lives.
- [AUTOSAR Classic Platform: Specification of NVRAM Manager (NvM), R23-11](https://www.autosar.org/fileadmin/standards/R23-11/CP/AUTOSAR_CP_SWS_NVRAMManager.pdf) — the layer above Fee: block management, write-all on shutdown, and why your shutdown time suddenly depends on flash.

### Articles and papers

A few sources on flash garbage collection, wear leveling, and AUTOSAR's NVM stack that go deeper into the mechanics touched on above:

- [Explained: Garbage Collection — Swissbit](https://www.swissbit.com/en/blog/post/Explained-Garbage-Collection/)
- [Fundamentals of NVM in AutoSAR Part-1 — dev.to](https://dev.to/kumar001repo/fundamentals-of-nvm-in-autosar-part-1-1620)
- [Flash EEPROM Emulation (FEE in AUTOSAR) — embeddedtutor.com](https://www.embeddedtutor.com/2020/05/flash-eeprom-emulation-fee-in-autosar.html)
- [AURIX MCU: Avoiding GC during FEE boot up in TC3xx MCAL — Infineon Developer Community](https://community.infineon.com/t5/Knowledge-Base-Articles/AURIX-MCU-Avoiding-GC-during-FEE-boot-up-in-TC3xx-MCAL-KBA236204/ta-p/369740)
- [AURIX MCU: Garbage collection in FEE MCAL driver — Infineon Developer Community](https://community.infineon.com/t5/Knowledge-Base-Articles/AURIX-MCU-Garbage-collection-in-FEE-MCAL-driver/ta-p/371131)
- [What is Wear Leveling and Garbage Collection in SSDs? — FutureScope](https://www.futurescope.co/wear-leveling-and-garbage-collection-in-ssd/)
- [Garbage collection and wear leveling for flash memory: Past and future — IEEE Xplore](https://ieeexplore.ieee.org/document/7043841/)
- Eran Gal, Sivan Toledo: [*Algorithms and Data Structures for Flash Memories*](https://doi.org/10.1145/1089733.1089735), ACM Computing Surveys 37(2), 2005 — the classic survey on log-structured flash storage, wear leveling and reclamation.
- Michael Nygard: [*Documenting Architecture Decisions*](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions), 2011 — the blog post that started the ADR format used for ADR-0001 above. More templates at [adr.github.io](https://adr.github.io/).

### Books

- Rino Micheloni, Luca Crippa, Alessia Marelli: *Inside NAND Flash Memories*, Springer, 2010 — NAND rather than NOR, but the best explanation of why cells wear out, what retention really means and why erase is so expensive.
- Elecia White: *Making Embedded Systems*, 2nd ed., O'Reilly, 2024 — has a solid chapter on memory and on designing for updates in the field.
- Jörg Schäuffele, Thomas Zurawka: *Automotive Software Engineering*, 2nd ed., Springer Vieweg, 2016 — the big picture of where flashing, production and the vehicle lifecycle meet.
