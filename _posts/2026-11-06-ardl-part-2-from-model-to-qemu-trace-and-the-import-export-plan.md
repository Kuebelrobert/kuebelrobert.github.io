---
layout: post
title: "ARDL, Part 2: From Model to QEMU Trace, and Working with OEM ARXML Deliveries"
date: 2026-11-06
categories: [System & SW Architecture]
tags: [autosar, ardl, toolchain, arxml, qemu, threadx, tracing, perfetto, import-export, oem, integration, architecture]
---

<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>mermaid.initialize({ startOnLoad: true, theme: "dark" });</script>

*This is Part 2 of a two-part post on ARDL. [Part 1]({% post_url 2026-11-06-ardl-part-1-design-as-code-for-autosar-classic %}) covered the idea, the checker, the OS view and how to start a project. This part runs the model on QEMU, draws the tasks and ISRs from a real trace, and shows how ARDL could handle AUTOSAR deliveries from an OEM when you build OS and BSW yourself: what it can do, and what is missing.*

A quick recap for people who skipped Part 1: [ARDL](https://marketplace.visualstudio.com/items?itemName=kuebelrobert.ardl) is a small VS Code extension that describes the structure of an AUTOSAR Classic system as text (interfaces, components, compositions, BSW modules, OS tasks and ISRs), checks the structural rules and draws the diagrams from the same model. It has no timing model, no code generator and, so far, no ARXML import or export. This part closes the first gap with a real run, and looks at what the import and export would have to do for a team that receives the application software from an OEM.

## From the model to a running system: QEMU and a trace

A model that only produces pictures has a credibility problem: nothing forces it to match reality. So I tried to close the loop. The example system from the [AUTOSAR-on-ThreadX posts]({% post_url 2026-10-20-running-autosar-on-threadx-part-1-os-and-execution-model %}), a body control unit with an ASIL B core and QM cores, exists as an ARDL model (see [Part 1]({% post_url 2026-11-06-ardl-part-1-design-as-code-for-autosar-classic %})): one OS per core, application tasks, BSW threads, and the supervision parts (timing protection, memory protection, trusted calls). The same system is also built into one image and **runs on QEMU** (a Cortex-M7 board model, with ThreadX underneath).

What that gives you in practice:

- **The code runs.** A self-test checks after five seconds what happened and ends QEMU with exit code 0 or 1. That makes it a regression test, not a demo.
- **Faults on demand.** Three injected scenarios: a task overruns its time budget, a QM component writes into ASIL data, and a component holds an OS interrupt lock for 10 ms. The protection hook, the memory fault handler or the lock monitor must react. Each run is deterministic because QEMU runs with instruction counting, so virtual time is the same on every run.
- **Linking found what compiling didn't.** Each snippet had compiled on its own for weeks. The first link-and-run found nine problems, among them interrupt locks that didn't lock on a BASEPRI-based port, and a restarted task that was charged its predecessor's budget overrun. Moral: a model, a compile check and a green CI do not replace running the thing.

Now the visualization part. A task and ISR timeline is the picture I want most when I debug scheduling, and QEMU makes it cheap. A small trace module records thread switches, category 2 ISRs and log lines into a RAM buffer (the ThreadX hooks are wrapped at link time, so the snippets stay untouched) and writes it out through semihosting at the end of the run. A script turns that into a trace file that opens in Perfetto or `chrome://tracing`. The tracks mirror the ARDL model: one group per core, one track per thread sorted by priority, one group for supervision threads and one for interrupts, with fault markers drawn across everything.

This is the lock scenario, redrawn from the real trace:

<figure style="margin:1.5rem 0">
<img src="{{ '/assets/images/ardl/qemu-lock-timeline.svg' | relative_url }}" alt="Timeline of ISRs and threads from a QEMU run. SysTick and the hardware counter interrupts tick regularly, then stop for 10 milliseconds while a single thread, Task100ms, occupies the CPU in one long slice. After it ends, the interrupts that piled up run in a burst." style="width:100%;max-width:900px;height:auto;display:block;margin:0 auto;border-radius:6px;background:#fff">
<figcaption style="font-size:0.9rem;margin-top:0.5rem">One lock, ten milliseconds. SysTick and the hardware counter go quiet, the timer thread goes quiet with them, and one thread keeps the CPU in a single 10.2 ms slice. When the lock is released, the interrupts that piled up run back to back. The watchdog thread, which needs those ticks, never serves the watchdog, and the run ends in the expected watchdog expiry.</figcaption>
</figure>

You would not find this in a code review. The structure is perfectly fine (the model says nothing about lock budgets), and the trace shows exactly the shape of the bug: a flat slice where a rhythm should be.

Two honest limitations of the QEMU setup: it has no multicore Cortex-M7, so both "cores" run on one CPU (the cross-core code paths run, but nothing races them), and the tables the snippets declare as generated, such as task, alarm and ISR configuration, are currently **written by hand** to match the model. Which brings me to the actual topic.

## Working with OEM deliveries: what ARDL could do, and what's missing

The setting I have in mind is common: the OEM delivers the application software as ARXML (SWC descriptions, interfaces, data types, often an ECU extract with the compositions and the communication) plus code or libraries, and you build the platform underneath it yourself. OS, RTE glue and BSW, maybe on ThreadX as in this example, **without a full AUTOSAR configuration tool suite.** Those tools exist for good reasons, but for a small team they're a lot of licence, training and lock-in for what is, at its core, a mapping problem: these runnables, these tasks, these ports, these signals.

ARDL can't do that today. **There is no ARXML import or export yet; everything below is a design, not a feature.** But most of what this workflow needs is structure, and structure is what ARDL already models and checks. So here is how it could look, and an honest list of the gaps.

### Who owns what

The split follows the delivery, element by element:

- **The OEM owns the components.** Interfaces, SWC types, runnables, their events and accesses, the compositions. In ARDL these become imported files: generated, read-only, never edited by hand, each element carrying its ARXML path as provenance.
- **You own the platform.** OS, task mapping, exclusive areas, BSW modules and their main functions. In ARDL these are hand-written files that reference the imported elements by name.

No element has two owners, so there's nothing to reconcile. A new delivery replaces the imported files, and the checker tells you where your hand-written part no longer fits.

<div class="mermaid">
flowchart LR
    OEM["OEM delivery<br/>(ARXML)"] -- import --> IMP["Imported ARDL<br/>(generated, read-only)"]
    OWN["Own ARDL<br/>OS, mapping, BSW"] --> CHK["Checker and diagrams"]
    IMP --> CHK
    CHK -- generate --> HDR["Rte contract headers"]
    CHK -- generate --> GLUE["Task bodies and OS tables"]
    HDR --> IMG["Image: OEM code + own platform"]
    GLUE --> IMG
    IMG -- trace --> TR["Timeline, conformance check"]
    TR -. against the model .-> CHK
</div>

### What it would look like

The importer turns ARXML into plain ARDL text. Shortened, for one OEM component:

```
// generated by ardl import from WiperCtrl.arxml (delivery 3.2), do not edit
interface sr WiperRequest { Mode: uint8 }
interface sr MotorCmd { Duty: uint8 }
interface cs Calib { GetValue(in id: uint16, out value: uint32): Std_ReturnType }

swc application WiperCtrl {                  // /Oem/Body/Wiper/WiperCtrl
    rport RpRequest : WiperRequest
    rport RpCalib   : Calib
    pport PpMotor   : MotorCmd
    runnable R_Init on init
    runnable R_Main every 10ms reads RpRequest calls RpCalib writes PpMotor
}
```

Your side is an ordinary ARDL file that maps those runnables to your OS and adds your BSW:

```
os Bcu profile threadx {
    task Init     on startup prio 2  core 1 runs WiperCtrl.R_Init
    task Task10ms every 10ms prio 11 core 1 runs WiperCtrl.R_Main, LightCtrl.R_Control
    task Bsw      every 5ms  prio 4  core 1 runs NvM.NvM_MainFunction, Com.Com_MainFunctionRx
}
```

The import itself is not where the value is. The value comes from what already works on that text:

- **A delivery diff you can read.** Delivery 3.3 arrives, you re-import, and `git diff` shows `runnable R_Main every 10ms` became `every 5ms` and a new port `RpDiag` appeared. No XML diff, no tool comparison report.
- **The checker as an integration review.** For that same diff, existing checks would already report: the period of `R_Main` is no longer a multiple of its task's period. `RpDiag` is an unconnected R-port. A new runnable `R_Diag` is not mapped to any task. That's exactly the list you need before the next integration build.
- **Diagrams of the delivery.** Compositions, component views and the OS view render straight from the imported model, including how the OEM's runnables sit in your tasks.
- **Lock and OS rules across the boundary.** Exclusive areas the OEM declares, resources you add, lock order, ISR rules and priority inversion are checked as one model.

### What ARDL can do today, and what's missing

| Needed for this workflow | ARDL today | What's missing |
|---|---|---|
| Interfaces, SWC types, ports | Yes, including e2e flags and all interface kinds | ARXML import |
| Runnables with events and accesses | Yes, including error and completion events, implicit access, exclusive areas | Import. Some details such as asynchronous calls |
| Compositions and connectors | Yes, with the structural checks | Import of the ECU extract's composition |
| Runnable-to-task mapping, OS objects | Yes, with completeness, period, lock and ISR checks | Nothing for the structure. Output toward ECUC or C, see below |
| BSW modules, layers, main functions | Yes, as structure | Configuration values (see below) |
| **Data types** | Names only (`uint16`, arrays) | Implementation and application data types, records, ranges, units, init values. Without these, no contract header can be generated |
| **Port details (com specs)** | No | Init values, queue lengths, timeouts, aliveness. The RTE needs all of them |
| **Communication to the bus** | No | Mapping of ports to system signals, PDUs and frames from the ECU extract. Anything that leaves the ECU depends on it |
| **Contract headers and RTE glue** | No generator | `Rte_<Swc>.h` per component, task bodies calling runnables in order, OS tables. This is the main piece of work |
| Calibration and multiple instances | `param` interfaces only | Parameter values, per-instance memory, multiple instantiation |
| Variants | No | Variation points in the delivery: pick one variant at import time, or map them to compile-time switches |
| Name collisions | Names are global | ARXML names are unique per package only. Needs a deterministic rename rule with a report, and in the long run packages in the language |
| Timing requirements, event chains | No, on purpose | Stays in the OEM's documents and in dedicated tools. The trace can check what the model declares, such as periods and mapping |

The order matters. The first four rows are mostly an importer away. Data types and com specs are what turns "nice diagrams of the delivery" into "OEM code compiles against my platform". The bus communication decides whether this works for a real ECU or just for a demo.

### What should stay outside ARDL

The tempting mistake is to grow ARDL until it is the configuration tool it was meant to avoid. Three things I'd keep out:

- **BSW configuration values.** The settings for Com, PduR, CanIf, NvM or Dem are mostly tables derived from the communication matrix and the diagnostic description. A small generator that reads those directly from the delivery fits better than an ARDL syntax for every parameter. ARDL keeps the structure: which modules exist, who uses whom, which main function runs where.
- **Type details in the grammar.** Data types and com specs are needed for generation, but nobody has to read them in a diagram. The importer can keep them in a machine-readable side file per delivery, keyed by the element's ARXML path, and the generator joins both. The language stays small and readable.
- **Timing.** Same position as in Part 1. A trace check against declared periods and mappings is cheap and honest. A schedule analysis is a different tool.

### The way back to the OEM

What the OEM wants back varies. Often it's not ARXML at all, but proof that the integration is complete and consistent. ARDL can produce two things with little effort:

- **An integration report** from the checker: every runnable mapped, every R-port connected, every rename at import, every element the importer did not map. Nothing is dropped silently.
- **The task mapping as ECUC** (`Os` and the event-to-task mapping of the `Rte`) for the AUTOSAR profile, when the OEM or a later tool step needs it.

For any export, three rules apply. The output must be deterministic: sorted, stable formatting, UUIDs derived from the element path, so an unchanged model gives an unchanged file. It must survive a round trip: ARXML → ARDL → ARXML keeps everything ARDL can express. And it must validate against the schema of the targeted AUTOSAR release in CI.

### The order I'd build it in

1. **Import of SWC descriptions**, read-only, with `ardl import arxml <files> --emit` to print the generated text, provenance and a mapping report. This alone gives readable delivery diffs and the integration review.
2. **Data types and com specs** into the side file, so the importer keeps everything the RTE needs.
3. **Contract headers** (`Rte_<Swc>.h`). This is the first day the OEM code compiles against your platform, long before the platform runs.
4. **Task bodies and OS tables** for the ThreadX profile, replacing the hand-written tables of the QEMU image. As with any generated code without a qualified tool, it's a proposal that gets reviewed and tested.
5. **Port-to-signal mapping** from the ECU extract, and the generator for the communication tables next to ARDL, not inside it.
6. **Trace conformance** against declared periods and mappings.
7. **Packages in the language**, once real deliveries have shown what the name collisions look like.

None of these steps is a big tool. Each one is small, works on text in git, and can be checked in CI. If you receive AUTOSAR deliveries and build the platform yourself, I'd like to know which row of that table hurts you most. I suspect the answer is the bus communication, and I suspect real delivery files will prove a few of my assumptions wrong.
