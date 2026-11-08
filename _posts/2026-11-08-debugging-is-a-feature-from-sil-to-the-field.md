---
layout: post
title: "Debugging Is a Feature: Designing Diagnostics That Survive from SIL to the Field"
date: 2026-11-08
categories: [Debugging]
tags: [debugging, diagnostics, sil, pil, hil, field, reset-counter, hardfault, dtc, uds, flight-recorder, trace, mcp, ai, cortex-m7, architecture]
---

<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>mermaid.initialize({ startOnLoad: true, theme: "dark" });</script>

*The example in this post is the body control unit (BCU) from the [foundation series]({% post_url 2026-10-19-create-the-foundation-part-4-swc-allocation-and-task-setup %}): a Cortex-M7 with an ASIL B core and QM cores, running AUTOSAR-style software on ThreadX as in [Running AUTOSAR on ThreadX]({% post_url 2026-10-20-running-autosar-on-threadx-part-1-os-and-execution-model %}).*

Here's a bug report every embedded team has received in some form: *"Customer complaint: interior light flickers, then everything is dead for two seconds. Happened three times in four weeks. Workshop found no stored fault. ECU replaced, returned part shows no fault found."*

Translated: the BCU reset. Probably a watchdog, maybe a trap, maybe a brown-out. It happened weeks ago, in a car you'll never see, on a part whose debug port is locked, and since then the ECU has started up a few hundred times. Whatever the software didn't record at that moment is gone. No debugger, no trace, no luck.

This post makes one argument: **debugging in the field doesn't happen with a debugger. It happens with functions you built into the software years earlier.** Reset counters with context, trap records, extended DTC data, a small flight recorder. They cost a little RAM, a few NvM blocks and some agreement with the OEM's diagnostic spec, and they only exist if somebody planned them early. At the end there's a section on what AI assistants and MCP servers can add, and why they are only as good as the data you prepared for them.

## What's inside

- Why the field is the hardest debug target, and why it gets everything last
- The test levels: what you can see in MIL, SIL, PIL, HIL, production, the vehicle and the field
- The building blocks: reset reason and counters, trap records, supervision events, extended DTC data, a flight recorder, runtime counters
- One record format across all targets
- Production: clean field data, plant mode, traceability, early warnings
- Security: why debug data needs protection
- What "early" means, phase by phase, and what it costs
- Pitfalls that erase your evidence
- AI and MCP: where they help, and where a human stays in charge

## The field is a debug target too, just the worst one

Each step from the desk to the road makes the system more realistic and less visible:

| Level | What runs | Debugger | Trace | Reproducible | What you're missing |
|---|---|---|---|---|---|
| **MIL** | Models | Model debugger | Full | Yes | Real code, real timing |
| **SIL** | Production C code on a PC or emulator | Yes, full | Full, free | Yes | Real hardware, real interrupts, real memory |
| **PIL** | Code on the target CPU or an evaluation board | JTAG/SWD | On-chip trace (ETM/ITM) if you have the probe | Mostly | Real I/O, real bus load, temperature, supply |
| **HIL** | Real ECU, simulated vehicle | Often, if the port is open | Limited | Partly | Real vehicle, real customers, real time spans |
| **Production (ECU and vehicle plant)** | Production ECU, often still unlocked, on a tester or in a car on the line | Possible, but no time: seconds per unit | Tester logs per serial number | Statistically: thousands of units | Time to analyze anything, the real vehicle environment over months |
| **Vehicle (test fleet)** | Real ECU, real car | Rarely, cables in a car | Bus logs | Rarely | Thousands of cars, years of operation |
| **Field** | Production ECU, locked | **No** (and it shouldn't, see [Securing the Foundation, Part 3]({% post_url 2026-10-21-securing-the-foundation-part-3-code-debug-immobilizer-and-detection %})) | Only what the ECU records | No | Everything except what you built in |

The bugs don't care about this table. The interesting ones, the race that needs a specific bus load at minus twenty degrees during a voltage dip, show up at the bottom. So the instruments have to travel with the software, from the first SIL run to the last car on the road, and they have to be part of the production software, not a debug build.

Two consequences follow from that:

1. **Debug functions are product features.** They have requirements, a design, tests and a memory budget like any other feature. In a safety project, some of them (the watchdog, the protection hooks) are even safety mechanisms.
2. **The field defines the format.** Whatever the field can transport (DTCs, extended data, a few DIDs over UDS) is the format everything else should use too. A SIL trace in a completely different format means two decoders, two sets of IDs, and the field version is the one nobody tests.

## The building blocks

None of these are new. The point is to have all of them, with context, and consistently.

### 1. Reset reason and reset counters

Every reset has a cause, and most MCUs store it in a reset status register: power-on, brown-out, external pin, software request, watchdog (independent or window), lockup. Two rules:

- **Read it first, then clear it.** Before the startup code, the bootloader or the BSW initialize anything, the register must be copied. Some bootloaders clear it, and then the application always sees "software reset".
- **Count per reason, and keep a history.** A counter per reset reason in NvM tells you "this ECU had 47 watchdog resets". A short history ring tells you when and in which state:

```c
typedef struct {
    uint8_t  reason;         /* POR, BOR, PIN, SW, IWDG, WWDG, LOCKUP, TRAP, PROTECTION */
    uint8_t  mode;           /* ECU mode at reset: STARTUP, NORMAL, SLEEP_PREP, ... */
    uint8_t  task_id;        /* last running task, from the OS hook */
    uint8_t  detail;         /* e.g. ProtectionHook error code */
    uint16_t ign_cycle;      /* ignition cycle counter */
    uint16_t supply_mv;      /* last sampled supply voltage */
    uint32_t op_seconds;     /* operating time */
} reset_entry_t;             /* 12 bytes; 16 entries = 192 bytes of NvM */
```

The `mode` and `supply_mv` fields have saved me more often than the PC. "All watchdog resets happen in SLEEP_PREP at below 9 V" is a diagnosis. "Watchdog reset" alone is just a symptom.

Where does `task_id` come from after a reset? From RAM that survives the reset, see the next block.

### 2. Trap records: the moment of the crash

When the CPU raises a HardFault, MemManage or BusFault, the hardware has already pushed the evidence onto the stack: PC, LR, xPSR and the registers. The fault status registers (CFSR, HFSR, MMFAR, BFAR on a Cortex-M7) say what kind of fault it was and which address was involved. A trap record captures all of that, plus the software context, into a RAM section that the startup code doesn't clear:

```c
typedef struct {
    uint32_t magic;          /* TRAP_MAGIC: the record is valid */
    uint16_t format;         /* layout version, for the decoder */
    uint16_t reason;         /* HARDFAULT, MEMMANAGE, BUSFAULT, USAGE, WATCHDOG_EARLY, ASSERT */
    uint32_t build_id;       /* first 32 bits of the git hash: which ELF decodes this */
    uint32_t op_seconds;
    uint16_t ign_cycle;
    uint8_t  task_id, isr_id;
    uint32_t pc, lr, xpsr, sp;
    uint32_t cfsr, hfsr, mmfar, bfar;
    uint32_t stack[8];       /* top of the faulting stack, for a call-chain guess */
    uint32_t crc;            /* over everything above */
} trap_record_t;

__attribute__((section(".noinit"))) static trap_record_t trap_rec;

__attribute__((naked)) void HardFault_Handler(void)
{
    __asm volatile(
        "tst   lr, #4       \n"     /* which stack was in use? */
        "ite   eq           \n"
        "mrseq r0, msp      \n"
        "mrsne r0, psp      \n"
        "mov   r1, lr       \n"
        "b     trap_capture \n");
}

void trap_capture(const uint32_t *frame, uint32_t exc_return)
{
    trap_rec.pc   = frame[6];
    trap_rec.lr   = frame[5];
    trap_rec.xpsr = frame[7];
    trap_rec.sp   = (uint32_t)frame;
    trap_rec.cfsr = SCB->CFSR;   trap_rec.hfsr = SCB->HFSR;
    trap_rec.mmfar = SCB->MMFAR; trap_rec.bfar = SCB->BFAR;
    trap_rec.task_id = os_current_task_id();
    /* ... stack words (bounds-checked), timestamps, build ID, CRC, magic last ... */
    NVIC_SystemReset();
}
```

The handler does as little as possible: no flash writes, no DTC handling, no OS calls. It writes RAM and resets. The **next startup** does the rest: if the magic and the CRC are valid, it copies the record to an NvM ring, sets a DTC with extended data (block 4), and clears the magic. This split matters. A fault handler that tries to write flash is a second fault waiting to happen.

The `build_id` makes the record decodable years later: it tells you exactly which ELF and map file translate `pc = 0x0802A3C4` into a function and a line. That means **archiving the ELF of every released build**, which sounds obvious until you need the one from the hotfix three years ago.

### 3. Supervision events: the faults you caught yourself

In the BCU, the OS layer detects problems before the CPU does: a task that overruns its time budget, a QM component writing into ASIL memory, an interrupt lock held too long, a missed alive checkpoint. Each of these ends up in the ProtectionHook or the watchdog supervisor (see [Part 1 of the ThreadX series]({% post_url 2026-10-20-running-autosar-on-threadx-part-1-os-and-execution-model %})). That's the right place to record *what* was violated, with numbers:

- **Timing protection:** which task, its budget, the measured time.
- **Memory protection:** which task, the address, the MPU region.
- **Lock monitor:** which task held the lock, for how long, and the lock budget.
- **Alive supervision:** which checkpoint was missing, and the count per supervision cycle.

When the [BCU example ran on QEMU]({% post_url 2026-11-06-ardl-part-2-from-model-to-qemu-trace-and-the-import-export-plan %}), these were exactly the log lines that made the injected faults understandable: *"ProtectionHook: E_OS_PROTECTION_TIME"* is a start, *"Task100ms: 50 ms, budget 20 ms"* is a finding. In the field, the same information goes into the extended data of a DTC instead of a log line.

### 4. Extended DTC data: the field's only mailbox

Diagnostics over UDS is the one channel to a production ECU that every workshop has. It offers three places for debug information:

- **Snapshot data (freeze frame), service 0x19 with subfunction 0x04:** environment values at the moment the DTC was set. Voltage, temperature, mode, operating time.
- **Extended data records, 0x19 with subfunction 0x06:** counters and anything else defined per DTC. Occurrence counter, aging counter, and, for an internal software error DTC, the decoded essentials of the trap record or the supervision event.
- **Manufacturer-specific DIDs, service 0x22:** the reset history, the per-reason counters, CPU load per task, stack high-water marks, the last N trap records.

A pattern that works: a small number of **internal software error DTCs** (trap, timing protection, memory protection, watchdog, NvM consistency), each with an extended data record carrying the context fields from blocks 1 to 3, plus one DID that returns the full raw record for the decoder. The DTCs make the problem visible in every workshop. The DID gives the developer the details.

The catch: **DTCs, their extended data and the DIDs are part of the OEM's diagnostic specification.** They show up in the diagnostic database, the workshop tester and often in the end-of-line test. Adding them after the diagnostic freeze ranges from painful to impossible. That alone is the strongest argument for planning debug functions in the concept phase.

Two more things to settle with the OEM: debug DIDs must sit behind the right security level (they reveal memory layout, which helps an attacker, see [Securing the Foundation, Part 2]({% post_url 2026-10-21-securing-the-foundation-part-2-updates-bus-and-diagnostics %})), and none of the records may contain personal data or keys.

### 5. A flight recorder: the seconds before

A trap record shows the moment of the crash. Often you need the story leading up to it: which task ran before, which bus message arrived, which mode switch happened. A flight recorder is a small ring buffer in non-cleared RAM with the last few hundred events:

- task switches and ISRs (from the OS hooks, as in the QEMU trace),
- mode changes and state machine transitions,
- communication errors, E2E failures, timeouts,
- the supervision events from block 3.

At 12 bytes per event, 2 to 4 KB hold the last 200 to 300 events, roughly the last few hundred milliseconds at full detail, or much longer if task switches are left out. On a trap the recorder freezes, and the next startup saves it with the trap record.

The trick is to use **exactly the event format of the SIL and QEMU trace.** Then the same converter turns a field recorder dump into the same Perfetto timeline you know from your desk, with the same track names. The picture of a 10 ms interrupt lock looks the same, whether it came from QEMU or from a car.

### 6. Runtime counters: the slow problems

Not every problem crashes. Some just get worse: a queue that fills up a little more every month, a stack that comes within 40 bytes of its end once a year, a CPU load that creeps up with every feature. Cheap counters catch those:

- stack high-water mark per task (painted stacks, checked in the idle task),
- maximum queue fill level per queue,
- CPU load per task and per core, as a peak and a long-term average,
- maximum lock duration per lock, maximum interrupt latency,
- retry and error counters per communication channel.

They cost a few bytes each, they're readable by DID, and they turn "we think we have margin" into a number from real vehicles.

## One record, every target

The building blocks only pay off if the information stays the same from target to target. Same structure, same IDs, same decoder. Only the transport differs:

<div class="mermaid">
flowchart LR
    REC["Records<br/>reset, trap, supervision,<br/>flight recorder, counters"]
    REC -- "SIL: file" --> DEC
    REC -- "QEMU: semihosting" --> DEC
    REC -- "PIL / HIL: debugger, XCP, UART" --> DEC
    REC -- "Vehicle and field: UDS DTCs and DIDs" --> DEC
    ELF["ELF and map file<br/>per build ID"] --> DEC
    DEC["One decoder<br/>(in the repo, tested in CI)"] --> OUT["Report, Perfetto timeline,<br/>symbolized call chain"]
</div>

Rules that make this work:

- **Versioned formats.** Every record carries a `format` field. The decoder supports all versions that ever shipped.
- **Build ID in every record.** Without it, a PC value from the field is just a number. The lifecycle state (plant or field) belongs there too, and the serial number at least next to it.
- **One timestamp model.** Operating time, ignition cycle and milliseconds since boot. In SIL these are simulated, but they exist, so the decoder doesn't need special cases.
- **IDs instead of strings.** Error IDs, task IDs and event IDs are numbers defined in one place, generated into the C code and into the decoder. Strings in a 2 KB buffer are a luxury the field can't afford, and they can't be translated back reliably.
- **Tested end to end in CI.** In SIL or on QEMU, inject a fault, let the ECU reset, read the records back through the same diagnostic path the workshop uses, decode them, and check the result. The QEMU fault scenarios from the BCU example are this kind of test, and they found real bugs in the protection mechanisms whose events are recorded. If the chain isn't tested, it breaks silently, and you find out on the first real field return.

## Production: the forgotten target

Between the HIL and the customer's car sits a stage most debug concepts forget: production. Twice, in fact. The ECU supplier builds and tests the unit (board test, functional test, flashing, end-of-line test), and the vehicle plant installs it, flashes or codes it on the line, and runs its own end-of-line test in the finished car. Production is a debug target with unusual properties: thousands of units, a few seconds per unit, debug access often still open, and nobody with time to analyze anything. It matters in three ways.

### Production pollutes the field data, unless you clean up

An ECU on its way through two plants sees more abuse than in its first year on the road: power removed mid-operation, connectors unplugged while the bus is active, flashing interrupted and restarted, test sequences that provoke faults on purpose. The result is a reset history full of brown-outs and software resets, internal error DTCs set by the test itself, and runtime counters with peaks from the test bench.

If nobody clears this, the field data starts polluted. "This ECU had 23 brown-out resets" means nothing if 20 of them happened at the plant. So:

- **A defined reset of the debug data at the last end-of-line step**, through a diagnostic routine (UDS service 0x31) behind a security level, so a workshop can't erase a field history by accident. Reset counters, history, trap records, runtime counters and the internal error DTCs start at zero when the vehicle leaves the plant.
- **Keep what the plant saw before deleting it.** The end-of-line tester reads the records first and stores them in the plant database with the serial number. A trap in production is the cheapest field failure you'll ever find.
- **Mark the boundary.** Store the operating time and ignition cycle at the reset, so later records can be read as "x hours after delivery".

### Plant mode and field mode

Many ECUs have a lifecycle state: a plant or transport mode with open debug access, relaxed supervision or reduced functions, then the locked field state (see the lifecycle section in [Securing the Foundation, Part 3]({% post_url 2026-10-21-securing-the-foundation-part-3-code-debug-immobilizer-and-detection %})). The debug functions have to know which state they're in:

- **Every record carries the lifecycle state**, so a trap from plant mode is never mistaken for a field issue.
- **Supervision stays active in plant mode** wherever possible. A watchdog that's disabled for production hides exactly the problems production could have found.
- **The switch to field mode is an end-of-line step**, and an ECU that leaves the plant still in plant mode needs a DTC of its own. It happens more often than anyone admits.

### Traceability: linking a field return to its production history

A trap record says what crashed. The production data says on which unit: serial number, hardware revision, software build, calibration data version, test station, date, component batches. Together they answer questions neither can answer alone:

- *"All 14 affected units were tested on station 3 in week 12."* A tester or fixture problem, not software.
- *"Only hardware revision C, only with the second-source flash."* A timing difference the software didn't tolerate.
- *"Every unit flashed with build 4.2.1 at the vehicle plant, none of those flashed at the supplier."* A flashing sequence problem.

This needs the serial number in every record the ECU sends (or at least readable by DID next to them), the plant database reachable by the people analyzing field returns, and the decoder able to join both. It's also the most useful data source for the MCP setup below: a "production data" server that answers "which units share this unit's batch and test history" turns one field return into a population.

### Production as an early warning system

The end-of-line data of the first production weeks is the first look at thousands of real units. Reset counters, trap records and runtime counters read at the end of line show:

- rare traps that the few HIL setups never hit,
- hardware spread: oscillator tolerance, flash timing, supply ramp-up behaving differently from the samples,
- stack and CPU margins on real units, not just the reference board.

None of this needs extra software, only the debug functions you already have, plus an end-of-line step that reads them and a person who looks at the statistics. Two practical constraints: the read-out has to fit the cycle time of the line, so keep the production read-out to a few compact DIDs, and the end-of-line routines have to be in the diagnostic spec and the tester sequence early, because plant test sequences are frozen long before SOP.

## What "early" means

"Plan debugging early" is easy to agree with and easy to postpone. Here is what it means concretely, per phase:

| Phase | Decide or do |
|---|---|
| **Concept** | Write debug requirements: which faults must be recorded, with which context, readable how and by whom. Reserve NvM and RAM. Agree with the OEM on the internal error DTCs, their extended data and the debug DIDs, and their security level |
| **Architecture** | Define a non-cleared RAM section and its placement. Decide who reads the reset reason before anyone clears it (bootloader or application). Hook points in the OS (task switches, ProtectionHook, watchdog) and in the BSW (Dem, NvM). Choose the record formats and the ID scheme |
| **Implementation** | Handlers that only capture and reset. Startup logic that validates and persists the records. Generated ID tables. The decoder, in the same repo |
| **Integration (SIL, QEMU, PIL)** | Fault injection for every recorded fault class, read back over the real diagnostic path, decoded in CI |
| **HIL and vehicle** | Same tests on real hardware: brown-outs, watchdog with the real window, ECC errors if the MCU can inject them |
| **Production ramp-up** | End-of-line routines for reading and resetting the debug data, in the diagnostic spec and the tester sequence. Lifecycle state switch from plant to field. Traceability data per serial number in the plant database, linked to the decoder. Read-out fits the cycle time |
| **SOP and field** | Debug port locked, debug data still readable through secured diagnostics. ELF and map file of every release archived with its build ID. A documented procedure for field returns |

And what it costs, roughly, for a BCU-sized ECU:

| Item | RAM | NvM |
|---|---|---|
| Reset counters and history (16 entries) | about 200 bytes | about 250 bytes |
| Trap record (current, plus 4 in NvM) | about 100 bytes | about 400 bytes |
| Flight recorder | 2 to 4 KB | 2 to 4 KB, only on a trap |
| Runtime counters | under 200 bytes | under 200 bytes |
| Code: handlers, startup logic, Dem integration, DIDs | | a few KB of flash |

That's a few kilobytes against weeks of guessing per field issue. The expensive part isn't the memory. It's the diagnostic spec negotiation, and that has a deadline.

## Security: debug data is attack data

Security and debugging pull in opposite directions, and both are right. The locked debug port is why the built-in functions exist at all. But those functions open a door of their own, so they need the same care as any other diagnostic service (details in [Securing the Foundation, Part 2]({% post_url 2026-10-21-securing-the-foundation-part-2-updates-bus-and-diagnostics %}) and [Part 3]({% post_url 2026-10-21-securing-the-foundation-part-3-code-debug-immobilizer-and-detection %})):

- **Reading is protected.** PC values, stack words and memory addresses show an attacker the memory layout. Debug DIDs sit behind authentication (UDS 0x29, or 0x27 at least), and generic memory reads by address (0x23) are off in the field.
- **Deleting is protected and logged.** Clearing records erases evidence, for a careless workshop as much as for an attacker. The reset routine needs a security level, and the reset itself is recorded.
- **No secrets, no personal data in records.** Snapshot only what the decoder needs: no key material, no buffers that might contain it, no location or VIN beyond what the diagnostic spec allows.
- **Plant mode is a one-way door.** Switching back from field to plant mode must not be possible without authentication, or it's the easiest back door in the ECU.
- **Security events share the recorder.** Failed authentications, rejected messages and intrusion detection alerts use the same records and the same decoder.

## Pitfalls that erase your evidence

- **The startup code clears your section.** The C runtime zeroes `.bss`, and some startup files clear all of RAM. The non-cleared section must be outside both, and the linker script must say so.
- **RAM with ECC.** Many automotive MCUs need RAM initialized after reset to set up the ECC bits, often by hardware or the boot ROM. Find out what survives which reset type. Sometimes the answer is a dedicated backup or standby RAM, sometimes it's "nothing after a power-on reset, everything after a software reset".
- **The bootloader runs first.** It may use the RAM you reserved, clear the reset status register, or reset again on its own. Debug data needs an agreement between bootloader and application.
- **A fault in the fault handler.** A corrupted stack pointer makes the handler fault too, and the Cortex-M locks up. Keep the handler minimal, give it its own stack if possible (the main stack, with the faulting task on the process stack), and check bounds before reading stack words.
- **The watchdog resets during the dump.** Either the capture is faster than the shortest watchdog window, or you capture first and persist after the reset. The latter is safer.
- **A stack overflow overwrites the record.** Place the record where an overflowing stack can't reach it, or guard the stacks with the MPU so the overflow traps before it destroys anything.
- **Too many DTCs, too much noise.** If every hiccup sets a DTC, workshops learn to clear them. Keep the internal error DTCs few and meaningful, and put the details in extended data and counters.
- **No ELF for the build.** The most avoidable pitfall of all. Archive it with the release, keyed by the build ID.

## AI and MCP in debugging

Most of debugging is reading and correlating: a record, a map file, the source at that line, a trace, the history of similar issues. That's exactly the kind of work current AI assistants are good at, as long as they can reach the data. The **Model Context Protocol (MCP)** is the plumbing for that: a standard way to give an assistant tools. An MCP server wraps one system and exposes a few well-defined operations, and the assistant decides when to call them.

For embedded debugging, useful servers would be:

| MCP server | Operations | Typical use |
|---|---|---|
| **Diagnostics** | Read DTCs, snapshot and extended data, read DIDs | Pull the trap record and reset history from an ECU on the bench or via the tester |
| **Build archive** | Fetch the ELF and map file for a build ID | Symbolize a PC, LR and stack words into functions and lines |
| **Decoder** | Decode raw records into structured data | The same decoder as in CI, so the assistant never parses bytes itself |
| **Trace** | Query a trace with SQL (Perfetto's trace processor can do this) | "Which task ran longest before the reset?", "When did SysTick stop?" |
| **Debugger** | GDB, OpenOCD or pyOCD: halt, read memory and registers, set breakpoints | PIL and HIL sessions, reading a live fault state |
| **Bus logs** | Search CAN or Ethernet captures by time and ID | Correlate a reset with bus traffic before it |
| **Issue tracker** | Search and link earlier reports | "Same build, same PC, three other field returns" |
| **Production data** | Look up a serial number: build, hardware revision, test station, batches, end-of-line records | "Which other units share this unit's batch and test history?" |

With those in place, a field return could go like this. The assistant reads the internal error DTC and its extended data and fetches the matching ELF by build ID. It symbolizes the call chain, reads the code around it, looks up the unit's production history, and checks the flight recorder: the last events before the trap were a mode switch to SLEEP_PREP and a queue overflow. Then it finds two earlier tickets with the same PC and writes a SIL or QEMU scenario that reproduces the sequence. It runs it and compares the resulting trace with the field recorder. The human gets a hypothesis with evidence, a reproduction and a diff of two timelines, instead of a hex dump.

That loop isn't hypothetical in its small form. When I brought the BCU example up on QEMU, an AI coding assistant ran exactly this cycle: run, read the log and the trace, form a hypothesis, change one thing, run again. It found several of the problems listed in the [ARDL post]({% post_url 2026-11-06-ardl-part-2-from-model-to-qemu-trace-and-the-import-export-plan %}), among them interrupt locks that didn't lock. What made that possible wasn't the model, it was the deterministic emulator, the structured log lines and the trace.

That's the real connection between this post's two halves: **AI makes good debug data much more valuable, and does almost nothing for bad debug data.** A versioned, decoded, symbolizable record is something an assistant can reason about. A string buffer of half-overwritten printf output isn't. Everything in the first part of this post is also preparation for the second.

### Where a human stays in charge

| Task | AI can help | Human stays responsible |
|---|---|---|
| Reading and correlating records, traces, logs | Yes, fast and thorough | Checking that each claim points to a record, a trace line or a line of code |
| Proposing root causes | Yes, several, ranked | Deciding which one is true. Plausible isn't proven |
| Writing reproduction scenarios | Yes | Judging whether the reproduction really matches the field |
| Proposing fixes | Yes | Review, impact analysis, safety argument |
| Writing to the ECU: flashing, clearing DTCs, writing DIDs, routine control | **No, not autonomously** | Every write, every time |
| Controlling a HIL with real actuators | Read-only at most | Anything that moves a motor, a window or a wiper |

A few rules I'd set before connecting any assistant to a bench:

- **Read-only by default.** Diagnostic and debugger MCP servers expose reading operations. Writing operations are a separate server that's off unless a human enables it for one session.
- **Evidence or it didn't happen.** Ask for the record, trace query or code line behind every statement. Assistants produce fluent, confident explanations, and in debugging a fluent wrong explanation costs more than none.
- **Know where the data goes.** Field data can contain the VIN, timestamps and location-related information. Source code and ELF files are confidential. Use models and hosting your organization has approved for that data, and strip what isn't needed.
- **Determinism helps the machine as much as the human.** A reproducible SIL or QEMU run turns an assistant's guess into an experiment. That's another reason to invest in the emulated targets.

## Checklist

- [ ] Debug requirements exist: which faults are recorded, with which context, how they're read, by whom
- [ ] Reset reason is read before anything clears it, and counted per reason with a short history
- [ ] Fault handlers capture into non-cleared RAM and reset; the next startup persists and reports
- [ ] ProtectionHook, watchdog and lock monitor record what was violated, with numbers
- [ ] Internal error DTCs with extended data and debug DIDs are in the OEM's diagnostic spec, behind the right security level
- [ ] A flight recorder uses the same event format as the SIL and QEMU trace
- [ ] Runtime counters for stacks, queues, CPU load and locks are readable by DID
- [ ] Every record carries a format version, a build ID and the lifecycle state; the ELF of every release is archived
- [ ] The end of line reads the debug data into the plant database, then resets it, and switches the ECU to field mode
- [ ] Production data per serial number is reachable by whoever analyzes field returns
- [ ] One decoder for all targets, in the repo, tested in CI with fault injection over the real diagnostic path
- [ ] Debug reads need authentication, deleting is protected and logged, records hold no secrets
- [ ] Assistants and MCP servers get read-only access by default, and every finding comes with its evidence

The debugger is the tool for the first half of the project. For the second half, the production ramp-up and the years after SOP, the tools are the ones you built into the software. Build them while you still can.
