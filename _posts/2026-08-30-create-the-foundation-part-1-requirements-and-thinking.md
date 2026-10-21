---
layout: post
title: "Create the Foundation, Part 1: Requirements Research and the Thinking Process"
date: 2026-08-30
categories: [System & SW Architecture]
tags: [architecture, project-foundation, technical-debt, security, communication, updateability, diagnostics, autosar, cortex-m7]
---

*This is Part 1 of a series on laying the foundation for a new ECU project. Part 1 covers requirements research and the thinking process; [Part 2]({% post_url 2026-09-03-create-the-foundation-part-2-memory-mapping-and-partitioning %}) covers memory mapping and partitioning; [Part 3]({% post_url 2026-09-04-create-the-foundation-part-3-protection-allocation-and-cpu-load %}) covers memory protection — MPU, bus masters and peripherals; [Part 4]({% post_url 2026-10-19-create-the-foundation-part-4-swc-allocation-and-task-setup %}) covers SWC allocation, a first CPU budget and a first task setup.*

Starting a new ECU project typically begins with compiling code for an A-Sample without much in the way of requirements — usually just the purpose of the ECU (BCU, Gateway, BMS, etc.) and, if you're lucky, a derived ASIL (the automotive safety integrity level).

The first priority is getting a first commissioning of the individual parts — the microcontroller, the safety companion chip, sensors and actuators — via IO testing to confirm the PCB wiring is correct, setting up a test environment like a HIL, and taking first measurements on how the sensors and actuators behave in real life.

This means the top priority goes to hitting those goals, which often means neglecting the vital parts — memory layout, partitioning, and design patterns — that a project actually needs to succeed in the long run. That's the first step into technical-debt hell: debt that, in reality, never gets paid back, because no customer is going to pay you to fix something they can't see.

To use an analogy: imagine someone building a house without a detailed plan, knowing only that it will be a house — sometimes without even a stable foundation, just so they can install windows and doors first.

Every homeowner would go after the architect and construction company with a shovel if their house were built that way.

Especially in these modern days, where AI is spitting out more code than a human can read in a day!

So a solid foundation — even when the requirements aren't 100% ready — might not be such a bad idea after all.

In most of the projects I've had the luck of contributing to, the SW stack was customizable, or built around something called a "platform", so you were already able to start from a "solid" foundation. You take a project you (hopefully) already pushed somewhere safe, and start by forking or branching it for the upcoming project.

You start by removing everything that's no longer needed and aligning the old project to the new hardware.

Modify the bring-up, change some IOs, remove the unwanted runnables, deactivate most of the safety features, and so on.

This approach speeds up getting a running SW on the new sample — as long as the foundation is robust and the architecture actually lets you do it (a topic for another post: clean architecture :)). The memory mapping usually gets adapted slightly, while the key principles behind the partitioning and memory protection concept get carried over as-is.

Wait a minute — didn't I just say technical debt never gets paid back? Right. So yes, that debt is about to become part of your new architecture too. Yippee-ki-yay, brothertrucker, if you know what I mean.

Writing all this down, I'm starting to think SW projects work a lot like the real-world financial system :O.

So let's forget that approach for the rest of this series, since not everyone has the luxury of just copying a disastrous project and trying to make it work :D. Let's build one from scratch instead — properly, starting with the thinking, not the flashing.

## Lay out the foundation

Let's assume you're lucky enough to be the SW architect for a BCU (Body Control Unit) on an A-Sample, with a safety requirement to support ASIL B.

Typical functions include things like immobilizer, lighting, climate & thermal, parking assist, and so on.

It's an ARM Cortex-M7-based automotive MCU, in the same vein as the safety-oriented multi-core families several vendors now offer: six Cortex-M7 cores running at around 300 MHz, with a chip-level safety story that supports ISO 26262 up to ASIL D — *if* you pair two of the cores up in lockstep. That pairing isn't fixed in silicon, it's a configuration choice: you decide whether to sacrifice cores in pairs to buy hardware-checked redundancy, or run all six independently for more raw compute.

Our project only needs ASIL B. Lockstep buys you ASIL D-grade confidence at the cost of a whole core's worth of throughput — and for ASIL B, that's usually more insurance than you need. So the plan for this project is: one core runs simplex as our ASIL B core (software-diagnosed — periodic self-tests, ECC-protected memory, the usual toolbox — instead of a hardware-compared twin), and the other five run as independent QM cores. Same chip that could give us one ASIL-D-grade core and four spare, now gives us one ASIL-B-grade core and five QM cores instead. Over-qualified hardware for the software requirement, deliberately spent on throughput instead of on safety margin we don't need — which, again, is a very normal, very common outcome of hardware being locked in before requirements are.

One warning before you celebrate the extra throughput: "simplex ASIL B with software diagnostics" is a much bigger decision than it sounds. ASIL B still demands real fault coverage for the CPU itself, and on a core without a lockstep twin, that coverage comes from a software test library that periodically exercises the core and costs CPU time on exactly the core you care most about. Worse, many MCU safety manuals simply *assume* lockstep for any ASIL use. So the first document to read isn't the datasheet, it's the chip's safety manual and its assumptions of use: does the vendor support ASIL B on a simplex core at all, with which test library, and at what CPU cost? If the answer is "no", your architecture just changed before it started.

Projected memory usage is sufficient, so no bottleneck there. Projected CPU load, however, is unknown — hardware, system or most likely the customer's purchasing department made that decision on its own, without knowing the actual load (and let me assure you, that happens a lot more often than you'd think — we'll come back to that particular gift later in this series).

Besides ASIL B as a safety goal, you have the usual standard requirements: security, communication (let's assume for the sake of the example: four CAN FD, eight LIN and one Ethernet channel), OBD relevance, updateability, and some diagnostics. Nothing fancy, but still painful if you don't consider it in the foundation.

Any further discussion about hardware changes is pointless — the schematic is frozen, the B-Sample is already in the making. That's automotive for you.

So what's the first thing you need to do, besides cancelling all vacation for the next three years, since "taskforce" is written all over this project?

You start by trying to get as much information as possible about further requirements, or details on the ones that already exist — but don't waste time just waiting for answers.

You need to be bold: assume requirements where you have to, or just decide to design the project the way you think is right. I know that's easier said than done, and experience helps, but if you don't decide, deadlines will decide for you. I can assure you deadlines and technical debt are siblings in the project world.

So: gather as much information as you can within a defined time window, and then set the foundation. There's usually no truly wrong decision, though of course some solutions work better than others. Either way, your team and your customer will thank you for it — and honestly, it's also just your job!

Let's take a closer look at what you actually need to research and decide before you can draw a single line of your memory map — because every one of these decisions ends up carved into it.

## Security — secure as Fort Knox, but slow and resource-hungry

Security is important, and every ECU has security goals. Clarify which security mechanisms you actually need to implement. Secure boot and authenticated boot have completely different impacts on startup behavior. Secure boot requires a root of trust, which means a handshake between the boot manager (or first-stage bootloader) and the security module. Think carefully about what's really needed — the impact on your foundation can be severe, affecting memory mapping and startup time, just to name a couple.

## Communication — the first "hello world" that actually matters

Communication is crucial for an ECU — without it, it's just a piece of electronics. Clarify the security and safety requirements on your communication channels. SecOC and E2E protection are standard by now, so you already need to think about where to allocate your ComStack. You should also consider whether it's worth splitting up your Com main functions to reduce CPU load. Keep in mind that you'll need to route received signals into various components, so your memory protection scheme needs to be capable of handling that. Most ECUs need communication up and running very early during startup, so plan for that in your init sequence.

## Updateability — OTA as your life insurance

Let me start with the most important point: you need a solid plan for updating your SW throughout the development lifecycle. This is one of the biggest lessons I've taken away from the last few years. Of course, OTA isn't the only way to update your SW, especially not in the early phase — but at some point, and usually earlier than you'd think, you'll need to be updateable through the official update tools: OTA, an offboard tester, or similar. At the very beginning you might get away with a debugger, or maybe XCP or something proprietary — but plan this thoroughly, or you'll be in real trouble. Cars are meant to drive, and once they're driving, nobody wants to carry a debugger around just to update them.

Furthermore, updateability has a huge impact on your SW architecture. You need to consider integrity and authenticity mechanisms in the memory layout — a CRC check for integrity, or a proper signature for authenticity, which are two different things (a CRC won't catch someone intentionally handing you the wrong image). You also have to consider which targets need to be updateable, like the application and the flash bootloader. If the application contains calibration data — which it usually does — you might need to split code from calibration. One hint I'll already give you: think about how to divide your targets into updateable blocks. Depending on the microcontroller's memory architecture, it can make sense to have more than two blocks that can be updated separately — just be aware that each block adds the overhead of being validated, and the risk of failing during the update.

And first and foremost, check whether you need to support an A/B swap mechanism, because that's a completely different approach from simply invalidating the application and flashing the new one over the old one.

## Diagnostics — your debugger once the hardware is out in the wild

By diagnostics I mean both the OBD standard — determined by the legislation of whichever countries the car is sold in — and sensor or general ECU diagnostics that determine the system's specific state. OBD can be quite CPU- and memory-intensive depending on the used OBD fault classes, since it demands a lot of features to be implemented. So always find out whether you really need OBD, which OBD fault classes you need to implement, or whether you have room to negotiate the requirements down. Sensor diagnostics, and especially general diagnostics, can be a lifesaver once you have problems in the field. Always consider diagnostic services, or at least DTCs, that let you capture important information about the ECU's internal state before the problem occurred — you'll need them if the problem is a sporadic one. OBD lets you define your own trouble codes, stored in a format that helps you pinpoint the error source. Clarify how you want to recover from diagnostic abnormalities — this is often already defined by the customer, but it's still worth considering early, while you're designing your internal state machine.

## Low power and startup time — the always-on ECU

A BCU is the ECU that never really sleeps. It has to wake up on a door handle, a key fob or a CAN message, it has to stay within a quiescent current budget measured in milliamps (sometimes less) while the car is parked for weeks, and it usually has to be talking on the bus within a few hundred milliseconds of waking up. Clarify early which wake sources you need, what has to survive a sleep (wake reason, reset reason, the last DTC), which core wakes up first, and whether partial networking is required. And put the startup time next to the security requirement: secure boot that verifies megabytes of application code before anything runs is great for security and terrible for "the bus expects an answer in 150 ms". You want to discover that conflict on paper, not on the first wake-up measurement.

## Memory protection hardware — the requirement hiding in the datasheet

This one is on nobody's requirement list, which is exactly why it belongs on yours. Every other topic above eventually ends up as a region in your memory map, and every one of those regions will eventually need to be *enforced* — by the MPU (or MMU) of each core that can reach it. So before you draw a single line, find out what shape of region your protection hardware actually accepts:

- **How many regions per core?** A Cortex-M7 typically gives you 8 or 16 MPU regions per core. That's not per memory type, that's *total* — flash, TCM, SRAM, standby RAM and peripherals all come out of the same handful of slots.
- **What does a region have to look like?** On the classic ARMv7-M MPU — the one a Cortex-M7 has — a region's size must be a power of two, and its base address must be aligned to that size. A 2 MB region can start at 0x01200000, but not at 0x01098000. A 1984 KB block is not one region at all; at an unlucky address it's six. (The newer Armv8-M MPU uses base/limit registers with 32-byte granularity and is far more forgiving — know which one you've got before you plan around either.)
- **What doesn't the MPU see?** A core's MPU only checks that core's own loads, stores and instruction fetches. DMA controllers, the HSM and other bus masters go around it, so those boundaries need a firewall at the crossbar or memory-controller level instead. Find out whether your chip has one, which masters it can tell apart (per DMA channel or only per DMA controller?), and its own granularity, alignment rules and number of rule slots, which are often coarser and fewer than the MPU's.
- **What are the flash sector sizes, and which flash blocks can work in parallel?** A boundary that doesn't sit on a sector boundary can't be erased on its own, and that breaks the independently updatable blocks you just asked for under updateability. One level up, check read-while-write: most flash can only be erased or programmed while you execute from a *different* physical block. If you want to update in the background while the car keeps working, your memory map has to follow those block boundaries too.

These are cheap constraints to respect while the memory map is still a blank page, and very expensive ones to retrofit: once the first software is out in the field, moving a region boundary means breaking compatibility with every update that's already out there. Put them on your list now, next to security and updateability, and treat them as requirements like everything else here.

These are only some of the considerations worth thinking about. A real ECU project is, of course, far more complex — I just wanted to share some thoughts based on what I've experienced so far.

## Where this leaves us

By now you should have a rough, honestly-assumed-where-necessary picture of your security approach, your communication needs, your updateability strategy, your diagnostic requirements, your power and startup budget, and the rules your memory protection hardware plays by. That's the input. None of it is memory layout yet — but every one of those six topics is about to become a constraint on it: security wants a protected root of trust region, updateability wants your flash split into independently updatable blocks, communication wants buffer space it can reach from multiple components, diagnostics wants somewhere persistent to write down what went wrong, low power wants memory that survives a sleep and a boot path short enough to wake up fast, and the MPU wants every region it will ever enforce to be a power of two, aligned to its own size.

In [Part 2]({% post_url 2026-09-03-create-the-foundation-part-2-memory-mapping-and-partitioning %}), we'll take exactly this BCU example and actually draw the memory map — flash layout, RAM partitioning across the ASIL B core and the five QM cores, and the reasoning behind where each of today's requirements ends up living.

Meanwhile, your colleagues are already fighting their first battles with bring-up SW — because getting the chance to debug on real hardware is a game changer, and nobody's going to wait for your memory map to be perfect before they start.

## Sources and further reading

### Standards and specifications

- [ISO 26262-1:2018 — Road vehicles — Functional safety — Part 1: Vocabulary](https://www.iso.org/standard/68383.html) — where ASIL, QM and "freedom from interference" are defined.
- ISO/SAE 21434:2021 — Road vehicles — Cybersecurity engineering — the frame for the security requirements and the TARA.
- [UN Regulation No. 156 — Software update and software update management system](https://unece.org/transport/documents/2021/03/standards/un-regulation-no-156-software-update-and-software-update) — why updateability is no longer optional.
- ISO 14229-1:2020 — Unified diagnostic services (UDS) — the diagnostic protocol behind the "debugger in the wild".
- [AUTOSAR Classic Platform: Layered Software Architecture, R23-11](https://www.autosar.org/fileadmin/standards/R23-11/CP/AUTOSAR_CP_EXP_LayeredSoftwareArchitecture.pdf) — a good map of which basic software module ends up owning which of the requirements above.
- [Arm: Armv7-M Architecture Reference Manual (DDI 0403)](https://developer.arm.com/documentation/ddi0403/latest) and [Armv8-M Architecture Reference Manual (DDI 0553)](https://developer.arm.com/documentation/ddi0553/latest) — the MPU rules that become memory-map requirements.
- [Arm: Cortex-M7 Technical Reference Manual (DDI 0489)](https://developer.arm.com/documentation/ddi0489/latest)

### Books

- Len Bass, Paul Clements, Rick Kazman: *Software Architecture in Practice*, 4th ed., Addison-Wesley, 2021 — quality attributes and how to turn vague wishes into requirements you can design against.
- Jörg Schäuffele, Thomas Zurawka: *Automotive Software Engineering*, 2nd ed., Springer Vieweg, 2016 — the automotive development process from requirements to series production.
- Hans-Leo Ross: *Functional Safety for Road Vehicles*, Springer, 2016 — ISO 26262 explained by someone who has to apply it.
- Joseph Yiu: *The Definitive Guide to ARM Cortex-M3 and Cortex-M4 Processors*, 3rd ed., Newnes, 2013 — the most readable introduction to the Cortex-M MPU, exceptions and low-power modes.
- Elecia White: *Making Embedded Systems*, 2nd ed., O'Reilly, 2024
