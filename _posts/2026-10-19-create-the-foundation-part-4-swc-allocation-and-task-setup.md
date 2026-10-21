---
layout: post
title: "Create the Foundation, Part 4: SWC Allocation and a First Task Setup"
date: 2026-10-19
categories: [System & SW Architecture]
tags: [architecture, project-foundation, swc-allocation, task-design, rtos, autosar, asil, cortex-m7]
---

*This is Part 4, the closing part of a series on laying the foundation for a new ECU project. [Part 1]({% post_url 2026-08-30-create-the-foundation-part-1-requirements-and-thinking %}) covered requirements research and the thinking process; [Part 2]({% post_url 2026-09-03-create-the-foundation-part-2-memory-mapping-and-partitioning %}) covered memory mapping and partitioning; [Part 3]({% post_url 2026-09-04-create-the-foundation-part-3-protection-allocation-and-cpu-load %}) covered memory protection; this part covers SWC allocation, a first CPU budget and a first task setup.*

So far, our BCU has a memory map the hardware can actually enforce and a protection concept that keeps QM away from ASIL B — cores, DMA, peripherals and all. What it doesn't have yet is software in it. One simplex ASIL B core and five QM cores, all of them empty, all of them waiting for somebody to decide what goes where — and, just as important, *when* it runs.

That's three decisions: which software component lives on which core, whether the CPU can actually carry it, and how each core's work is cut into tasks. Let's make all three, at least as a first draft you can defend in a review.

## SWC allocation: deciding what actually lives where

With the regions protected, the next question is which software component (SWC, in AUTOSAR terms) actually runs on which core, in which memory partition. This is a genuinely separate decision from the memory map — the map tells you what's possible, allocation tells you what you're actually doing.

The criteria I use, roughly in this order:

1. **ASIL classification first.** An ASIL B SWC goes on the ASIL B core, full stop. This isn't negotiable, and it's the one criterion that overrides all the others below.
2. **Communication locality second.** SWCs that talk to each other constantly are cheaper to run on the same core (or at least the same trust domain) than SWCs that rarely interact — every cross-core call through the shared region has overhead, and every one of them is a chance to hit the MPU boundary we spent a whole part locking down. This applies within QM too: two QM SWCs that chat constantly are still cheaper on the same QM core than split across two different QM cores, even though there's no MPU boundary between them — the inter-core overhead doesn't care whether both sides are QM.
3. **Timing criticality third.** A SWC with a hard real-time deadline benefits from sharing a core with as few other time-sensitive SWCs as possible, to keep scheduling analysis tractable. Mixing five different periodic tasks with tight deadlines onto the same core "because there's room" is how you end up debugging priority inversion at 2am.
4. **Load balancing last, not first — but now it's a real decision, not a formality.** With a single ASIL B core, there was never a choice about where ASIL work goes. With five QM cores, there genuinely is a choice about how QM work splits across Core 1 through Core 5, and that choice is worth making deliberately. Resist flattening load evenly before the first three criteria are satisfied — a perfectly balanced allocation that violates ASIL separation, or splits a tightly coupled QM communication chain across two QM cores for no reason other than a nicer-looking spreadsheet, is not actually a good allocation.

Write the allocation down as an actual table (SWC, ASIL level, core, rationale) rather than keeping it as tribal knowledge. You will revisit it more times than you expect, and "why is this here" is a much better question to answer from a table than from git blame on a config file from fourteen months ago.

### A first allocation for our BCU

Time to follow my own advice. Part 1 gave us the function list (immobilizer, lighting, climate & thermal, parking assist and the usual body stuff), four CAN FD channels, eight LIN channels, one Ethernet, diagnostics including OBD, and an update requirement. Let's assume the HARA left us with exactly one function that needs ASIL B: the exterior lighting that other road users depend on — brake lights, hazard lights and low beam. Everything else is QM. (That's an assumption, and like every assumption in this series it gets written down with a date. If the HARA comes back with a second ASIL function, this table is the first thing that changes.)

| Core | Role | SWCs | ASIL | Rationale |
|---|---|---|---|---|
| Core 0 | Safety | Exterior light safety (brake, hazard, low beam), hardwired brake pedal switch input, lamp output drivers and diagnosis, safety manager (fault reaction, safe state), E2E checks for ASIL-relevant signals, watchdog manager, self-tests, a small NVM handler for the ASIL B NVM block | ASIL B | Criterion 1. Also everything that *checks* the ASIL function lives here, not just the function itself. |
| Core 1 | Communication | CAN FD ×4, Ethernet, PduR/COM, SecOC, network management, gateway routing | QM | Criterion 2: every other core talks to the outside world through here, so routing stays on one core. |
| Core 2 | LIN & body | LIN master ×8 with schedule tables, window lifters, mirrors, wipers, seats | QM | Criteria 2 and 3: the body functions mostly *are* LIN slaves, and LIN schedule tables want a quiet, predictable core. |
| Core 3 | Comfort | Climate & thermal control, interior lighting, comfort functions | QM | Slow control loops with lots of calibration. Nobody here is in a hurry. |
| Core 4 | Parking | Parking assist: ultrasonic sensor timing, echo processing, distance warning | QM | Criterion 3: the one QM function with tight sensor timing gets a core mostly to itself. |
| Core 5 | Services | Diagnostics (UDS, DTC handling, OBD), NVM manager for the QM NVM block, immobilizer and HSM client, update manager | QM | Request-driven services with bursty load. Grouping them keeps their worst cases from colliding with anybody's control loop. |

Two things worth pointing out. First, the ASIL B core is deliberately not "the core with the lighting on it". It also hosts everything that supervises the rest: the safety manager, the watchdog manager and the self-tests from Part 3 (including the periodic readback of the MPU and firewall configuration). Second, the light *request* still arrives on Core 1, because that's where the CAN FD stack lives. So the most safety-relevant signal in the whole ECU crosses the ASIL/QM boundary on its way in. We'll come back to that below, because it decides a lot about the task setup.

## CPU load and memory consumption: the reality check nobody scheduled

Remember from Part 1 that hardware sized this microcontroller without knowing the actual CPU load? This is where that comes back to haunt you — or doesn't, if you plan for it properly.

Before we cut anything into tasks, one sober look at the budget. At this stage you don't have real measurements, because there's no running SW yet to measure. What you do have is the ability to make an honest first assumption instead of an optimistic one:

- **Base your first CPU budget on comparable past projects, not on this project's wishful thinking.** If a similar BCU generation ran at 60% load with a similar function set, "this one will surely be more efficient" is not a plan, it's a hope. Start from the closest real data point you have.
- **Reserve real headroom, not token headroom.** A common rule of thumb is to plan for 30-40% free CPU budget at this early stage, specifically because requirements will grow (they always do) and because interrupt load, communication overhead, and diagnostics tend to be underestimated across the board, not just by you.
- **Size stacks from worst-case call depth, not typical call depth.** This one is memory, not CPU, but the same discipline applies: a stack sized for the common case and blown by the one deep, rare, interrupt-nested call path is a bug that shows up in the field, not in your unit tests.
- **Write the assumption down as an assumption, with a date.** "We assumed X% load based on Y" is a sentence you want to be able to find again in six months, when the real measurements come in and either confirm you were reasonable or tell you exactly how wrong you were — and by how much.
- **Plan the first real measurement point explicitly.** Don't let "we'll measure it once bring-up is further along" be the whole plan. Decide now which milestone will produce your first real CPU load number, so the assumption above has a scheduled expiration date instead of quietly becoming permanent.

## A first task setup

An allocation tells you where things run. A task setup tells you when, and in which order, and what happens when something takes longer than planned. Get this one wrong and you can build a perfect spatial separation (Part 3) and still have QM interfere with ASIL — just through time instead of memory.

### The rules first

Before the tables, the rules the tables follow. These are the part I'd actually put into the architecture document:

- **One partition per task, never mixed.** A task runs either ASIL B code or QM code, never both. Part 3's second experiment showed why: the MPU protects per task, not per function, so a QM runnable inside an ASIL task runs with ASIL permissions.
- **A small, harmonic set of periods: 1, 5, 10, 20 and 100 ms.** Every period divides the next one, which keeps the scheduling analysis simple and lets cross-core data exchange line up on common boundaries. Somebody will ask for 50 ms. Somebody always does. It doesn't divide 20, so it gets 20 or 100.
- **Rate-monotonic priorities.** Shorter period, higher priority. The exceptions are event tasks for incoming communication, which sit just above the periodic task that consumes their data.
- **ISRs stay short and belong to the partition of their driver.** An ISR does the minimum and hands over to a task. QM drivers' ISRs run on QM cores only. Anything that needs microsecond timing (ultrasonic echoes, PWM edges) belongs in timer-capture hardware plus a short ISR, never in a task, not even a 1 ms one.
- **Hot code and stacks go into TCM.** Each core's tasks get their stacks and their most frequently executed code in that core's own TCM (Part 2): single-cycle access, no crossbar contention, and much easier timing analysis. Shared SRAM is for data that has to be shared, not for convenience.
- **Cross-core data moves at task boundaries, without locks.** The producer writes at the end of its task, the consumer reads at the start of its own, through the mailbox pattern from Part 3: single writer, sequence counter, CRC. No spinlock is ever shared between an ASIL and a QM task, because a QM task that holds a lock is a QM task that can stall the ASIL core.
- **Every task gets an execution budget, and somebody checks it.** The OS's timing protection (or a watchdog manager's deadline supervision) checks that each ASIL task finishes within its budget and on time. The watchdog manager on Core 0 also watches a heartbeat from each QM core. A dead QM core means degraded function, not a safe state, and that difference is a written-down decision, as Part 3 demanded.
- **Load per core stays at or below about 60% for now, interrupts included.** That's the 30–40% headroom from above, applied per core instead of averaged across the chip. Averaging is how you hide one overloaded core behind five relaxed ones. The budgets in the tables below are for task bodies, so the interrupt load (CAN FD receive interrupts on Core 1 can be a lot) has to fit into the gap between the table total and 60%.
- **Utilization isn't schedulability.** 60% load says nothing about whether the 5 ms task still makes its deadline when everything above it fires at once. Once real execution times exist, a worst-case response-time analysis per core replaces the percentages. Until then, the percentages are a sanity check, not a proof.

### Core 0 — ASIL B

| Task | Trigger | Priority | Content | Budget |
|---|---|---|---|---|
| `Init_Asil` | startup | — | MPU and firewall setup, startup self-tests, configuration CRCs | — |
| `Task_Asil_1ms` | 1 ms | highest | Lamp output monitoring (current feedback, open/short detection) | 8% |
| `Task_Asil_5ms` | 5 ms | high | Read brake pedal switch (debounced), read and E2E-check light requests, light arbitration, output commands | 15% |
| `Task_Asil_10ms` | 10 ms | medium | Safety manager, fault reaction, watchdog manager (alive, deadline and logical supervision) | 10% |
| `Task_Asil_100ms` | 100 ms | low | Periodic self-tests in slices: RAM test, MPU and firewall configuration readback | 12% |
| `Idle` | background | lowest | Flash CRC in slices | rest |
| | | | **Planned load** | **45%** |

### Core 1 — Communication (QM)

| Task | Trigger | Priority | Content | Budget |
|---|---|---|---|---|
| `Task_ComRx` | event (CAN FD / Ethernet Rx) | highest | Rx processing, SecOC verification, routing; writes ASIL-relevant signals for Core 0 | 18% |
| `Task_Com_5ms` | 5 ms | high | COM and PduR main functions (Rx/Tx), transport protocol | 15% |
| `Task_Com_10ms` | 10 ms | medium | SecOC main function, Ethernet stack | 12% |
| `Task_Com_100ms` | 100 ms | low | Network management, gateway housekeeping | 5% |
| | | | **Planned load** | **50%** |

### Cores 2 to 5 — the other QM cores

| Core | Task | Trigger | Content | Budget |
|---|---|---|---|---|
| Core 2 | `Task_Lin_5ms` | 5 ms | LIN schedule tables, all eight channels | 25% |
| | `Task_Body_10ms` | 10 ms | Window lifters (incl. anti-pinch), mirrors, wipers | 15% |
| | `Task_Body_100ms` | 100 ms | Seats, slow body functions | 5% |
| Core 3 | `Task_Comfort_20ms` | 20 ms | Interior lighting, comfort functions | 10% |
| | `Task_Climate_100ms` | 100 ms | Climate & thermal control loops | 25% |
| Core 4 | `Task_Park_1ms` | 1 ms | Ultrasonic burst sequencing (echo timing itself: timer capture + ISR) | 15% |
| | `Task_Park_20ms` | 20 ms | Echo processing, distance calculation, warning output | 30% |
| Core 5 | `Task_Diag_10ms` | 10 ms | Diagnostics (UDS, DTC handling, OBD) | 20% |
| | `Task_Svc_20ms` | 20 ms | Immobilizer, HSM jobs | 10% |
| | `Task_Svc_100ms` | 100 ms | Update manager, NVM manager | 15% |

Planned load, Core 2: 45%. Core 3: 35%. Core 4: 45%. Core 5: 45%. Every number in these tables is an assumption from comparable projects, not a measurement — exactly the kind the CPU budget section asked you to write down with a date, so it can be proven wrong on schedule.

### One signal, end to end: the brake light

Tables are nice, but a task setup only proves itself on a real signal path. Take the brake light. The request arrives from another ECU over CAN FD, and the lamp has to be on within (let's assume) 50 ms of it. On top of that, the BCU reads the brake pedal switch directly, through a hardwired input on the ASIL B core. That second source isn't decoration: it's diverse (different sensor, different path, no software from another ECU involved) and it never crosses the ASIL/QM boundary at all.

1. **Core 1, `Task_ComRx`:** the frame arrives, SecOC verifies it, and the signal is written into the shared workspace in SRAM Block 0, together with its E2E protection (sequence counter and CRC from the sending ECU). This is QM software writing data that ASIL will use — the amber cell from Part 3.
2. **Core 0, `Task_Asil_5ms`:** at the start of its next cycle, the ASIL task copies the signal, *then* checks the copy: E2E CRC, sequence counter, timeout. Only a valid copy goes into the light arbitration. An invalid or stale one is simply ignored, and the lamp follows the hardwired brake switch alone. Only if *both* sources are lost does the defined fallback kick in (for brake lights: assume braking, i.e. lamp on, which is the safe direction — and a DTC, so somebody actually finds out).
3. **Core 0, `Task_Asil_5ms`:** arbitration decides, and the output driver switches the lamp.
4. **Core 0, `Task_Asil_1ms`:** current monitoring confirms the lamp is actually on, or reports a defect.

Worst case from "frame received" to "lamp commanded": the Rx task's response time, plus up to one 5 ms period of waiting for Core 0's next cycle, plus the 5 ms task's own execution — call it about 10 ms on the ECU, well inside the 50 ms. More importantly, the latency is *bounded by design*: it depends on two task periods, not on how busy the QM cores happen to be. If Core 1 hangs completely, the ASIL side doesn't wait for it. It sees the timeout, keeps following the brake switch, and the watchdog manager reports the missing heartbeat. The car behind you never notices that half of your BCU just died, which is exactly the point.

That's what the rules above buy you. The safety-relevant path crosses the ASIL/QM boundary exactly once, at a fixed point in time, through a buffer slot only Core 1 writes, and the ASIL side validates everything it reads. And for the one function that really matters, there's a second path that doesn't cross the boundary at all.

### What this setup deliberately leaves open

A first draft that pretends to be final is worse than one that admits its gaps. Open for now:

- **Real execution times.** Every budget above is an estimate until the first measurement milestone from the CPU budget section.
- **Shared hardware.** The flash controller, the DMA controllers and the crossbar are shared by all six cores. Their contention shows up as timing jitter, not as a fault, and it needs measuring, not guessing.
- **Startup order.** Which core comes up first, who waits for whom, and how the ASIL core behaves while Core 1 is still initializing its communication stack. That deserves its own post.
- **The degradation concept.** What exactly happens to each function when a QM core is lost. The table of "dead core X → what still works" is a safety and a product decision, not just an architecture one.

## Closing out the foundation

Four parts ago, we started with nothing but a BCU, an ASIL B requirement, and a microcontroller whose CPU budget was decided by hardware without asking anyone. We turned that into a set of researched requirements, a memory map that traces back to every one of those requirements, an enforced protection scheme, a documented SWC allocation, an honest (if uncomfortable) first CPU budget, and a first task setup with one signal path traced end to end.

Is this foundation perfect? No — some of these assumptions will turn out wrong the moment real measurements show up. But it's a foundation you can explain, defend, and deliberately revise, instead of one that quietly accumulated by accident while everyone was busy getting the first sample to blink an LED. That difference is the whole point of this series.

## Sources and further reading

### Standards and specifications

- [AUTOSAR Classic Platform: Virtual Functional Bus, R23-11](https://www.autosar.org/fileadmin/standards/R23-11/CP/AUTOSAR_CP_EXP_VFB.pdf) — why SWCs can be allocated to cores late in the project, at least on paper.
- [AUTOSAR Classic Platform: Specification of Operating System, R23-11](https://www.autosar.org/fileadmin/standards/R23-11/CP/AUTOSAR_CP_SWS_OS.pdf) — tasks, alarms, schedule tables and multicore.
- [AUTOSAR Classic Platform: Specification of RTE, R23-11](https://www.autosar.org/fileadmin/standards/R23-11/CP/AUTOSAR_CP_SWS_RTE.pdf) — runnables and how they are mapped onto tasks.
- [ISO 26262-6:2018 — Product development at the software level](https://www.iso.org/standard/68388.html) — freedom from interference in the timing domain.

### Papers

- C. L. Liu, James W. Layland: [*Scheduling Algorithms for Multiprogramming in a Hard-Real-Time Environment*](https://doi.org/10.1145/321738.321743), Journal of the ACM 20(1), 1973 — the origin of rate-monotonic scheduling and its utilization bound.
- M. Joseph, P. Pandya: [*Finding Response Times in a Real-Time System*](https://doi.org/10.1093/comjnl/29.5.390), The Computer Journal 29(5), 1986 — response-time analysis, the tool to check the task setup against its deadlines.

### Books

- Giorgio C. Buttazzo: *Hard Real-Time Computing Systems*, 3rd ed., Springer, 2011 — the standard textbook for priority assignment, schedulability and resource sharing.
- Jane W. S. Liu: *Real-Time Systems*, Prentice Hall, 2000
- Hermann Kopetz: *Real-Time Systems: Design Principles for Distributed Embedded Applications*, 2nd ed., Springer, 2011 — time-triggered thinking, useful for the brake-light path end to end.
- Edward A. Lee, Sanjit A. Seshia: [*Introduction to Embedded Systems*](https://ptolemy.berkeley.edu/books/leeseshia/), 2nd ed., MIT Press, 2017 (free online) — scheduling and multitasking chapters.
