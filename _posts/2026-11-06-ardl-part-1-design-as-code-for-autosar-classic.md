---
layout: post
title: "ARDL, Part 1: Design as Code for AUTOSAR Classic, and How to Start a Project With It"
date: 2026-11-06
categories: [System & SW Architecture]
tags: [autosar, ardl, design-as-code, workflow, vscode, architecture, checks]
---
*This is Part 1 of a two-part post on ARDL. This part covers the idea, the checker, the OS view and how to set up a project with it. [Part 2]({% post_url 2026-11-06-ardl-part-2-from-model-to-qemu-trace-and-the-import-export-plan %}) covers the QEMU run, the trace visualization and how ARDL could work with ARXML deliveries from an OEM.*

Every AUTOSAR project has an architecture. Where it lives is the interesting question. In my experience it lives in four places at once: a slide deck from the kickoff, an ARXML file nobody dares to open without a tool, a configuration tool nobody dares to close, and the head of one colleague who is, naturally, on vacation.

I wanted a fifth place, and a boring one: **a text file in git**. This post is about that file format, [ARDL](https://marketplace.visualstudio.com/items?itemName=kuebelrobert.ardl) (AUTOSAR Design Language), a small VS Code extension I built for myself and then made public. This part covers what it is for, what it checks, how I use it to set up a project, and where it stops. [Part 2]({% post_url 2026-11-06-ardl-part-2-from-model-to-qemu-trace-and-the-import-export-plan %}) closes the loop with a QEMU run and a task/ISR trace, and lays out what I want to build next: import and export, because a design language that can't talk to ARXML is a hobby, and I'd like it to be at least a well-organized hobby.

## The intention: Mermaid, but it knows what a port is

The goal fits in one sentence: **describe the structure of an AUTOSAR Classic system as text, get the diagrams and the rule checks for free.**

Let me be precise about what that means, because "design tool" is a phrase that makes people reach for their wallets.

| ARDL is | ARDL is not |
|---|---|
| Text files you review in a pull request | A configuration tool for BSW modules |
| A checker for structural AUTOSAR rules | A code generator (today) |
| A diagram generator that can't get out of sync with the model | A timing analysis tool |
| Something a CI job can run in a second | A replacement for the ARXML your OEM sends you |
| Small enough to read in an afternoon | A qualified tool in the ISO 26262-8 sense |

The motivation was selfish. When I design an ECU, I want to answer questions like: which runnable writes this port, who reads it, which task runs it, and does that task share a lock with something that runs at a different priority? Those questions have exact answers in the model. Getting to the answers should not require a mouse, three dialogs and a license server.

The second motivation is review. A diagram in a slide deck can't be diffed. A text file can. "Why did the 10 ms runnable move to the 100 ms task?" is a question `git blame` can answer, and a screenshot can't.

## What it looks like

Three files describe one fictional light-control ECU in the examples. Here is the core of it:

```
interface sr Speed { Value: uint16 }

swc application LightCtrl {
    rport RpSpeed : Speed
    pport PpLamp  : LampState
    runnable R_Control every 10ms reads RpSpeed writes PpLamp
}

composition Body {
    prototype SpeedCalc
    prototype LightCtrl
    connect SpeedCalc.PpSpeed -> LightCtrl.RpSpeed
}

bsw NvM layer services uses MemIf
```

That's an interface, a component with ports and a runnable, a composition with a connector, and a BSW module with a layer. The grammar covers the vocabulary you'd expect from the RTE chapter of AUTOSAR: sender-receiver (optionally queued), client-server, mode and NV interfaces, the RTE events (`on init`, `on data`, `on call`, `on mode`, plus the error and completion events), explicit and implicit access, exclusive areas, E2E-protected ports, delegation and assembly connectors.

The editor does what editors do: syntax highlighting, completion, go to definition, find references, rename. The part I use most is the live preview next to the editor. It has a tab per view:

- **Composition view:** prototypes with their ports and connectors, data flowing left to right.
- **Component view:** one SWC with its ports, runnables, and which runnable touches which port.
- **Layers view:** BSW modules in the AUTOSAR layer bands, dependencies as arrows, upward dependencies in red.
- **OS view:** tasks, ISRs and the objects they share. More on this one below.

Because the diagram comes out of the same parse tree as the checks, there is no way for it to be out of date. This sounds like a small property until you've found a six-month-old architecture diagram that shows a connector somebody deleted last spring.

<figure style="margin:1.5rem 0">
<img src="{{ '/assets/images/ardl/lightctrl-component.svg' | relative_url }}" alt="Component view of an AUTOSAR software component named LightCtrl: required ports on the left, provided ports on the right, runnables in the middle with arrows showing which runnable reads or writes which port." style="width:100%;max-width:820px;height:auto;display:block;margin:0 auto;border-radius:6px;background:#fff">
<figcaption style="font-size:0.9rem;margin-top:0.5rem">The component view for <code>LightCtrl</code>, generated from the example file. Triangles are sender-receiver ports, rings are client ports, diamonds are mode ports.</figcaption>
</figure>

<figure style="margin:1.5rem 0">
<img src="{{ '/assets/images/ardl/body-composition.svg' | relative_url }}" alt="Composition view: software component prototypes drawn as boxes with their ports, connected by assembly and delegation connectors, data flowing from left to right." style="width:100%;max-width:820px;height:auto;display:block;margin:0 auto;border-radius:6px;background:#fff">
<figcaption style="font-size:0.9rem;margin-top:0.5rem">The composition view: required ports on the left, provided ports on the right, so the data flows the way you read.</figcaption>
</figure>

<figure style="margin:1.5rem 0">
<img src="{{ '/assets/images/ardl/bsw-layers.svg' | relative_url }}" alt="Layers view: basic software modules arranged in the AUTOSAR layer bands, services on top, ECU abstraction in the middle, microcontroller drivers at the bottom, with dependency arrows; an upward dependency would be drawn in red." style="width:100%;max-width:820px;height:auto;display:block;margin:0 auto;border-radius:6px;background:#fff">
<figcaption style="font-size:0.9rem;margin-top:0.5rem">The layers view of the same ECU's basic software. An upward dependency would show up in red, which is the diagram's way of clearing its throat.</figcaption>
</figure>

## The checker: the colleague who reads every line

The diagrams are the part people see. The checker is the part that earns its keep. ARDL encodes the structural rules I'd otherwise check in a review (or, more honestly, discover during integration). Here is a deliberately broken model and what `ardl check` says about it:

```
bad.ardl:18:33: error: Assembly target must be a required port; 'SpeedCalc.PpSpeed' is a P-port.
bad.ardl:18:5:  error: Interface mismatch: 'LightCtrl.PpLamp' is LampState, 'SpeedCalc.PpSpeed' is Speed.
bad.ardl:17:5:  warning: R-port 'LightCtrl.RpSpeed' is not connected.
bad.ardl:22:11: warning: 'Cfg' is shared by tasks of different priority without a protocol: priority inversion. Use 'protocol inherit' or a resource.
bad.ardl:23:14: warning: 'Ea1' is not used by any task or ISR.
bad.ardl:26:25: error: An ISR must not block: 'takes' can wait.
bad.ardl:26:31: error: 'takes' needs a semaphore; 'Cfg' is a mutex.
1 file(s), 4 error(s)
```

(I connected a P-port to a P-port of a different interface and then made an ISR wait on a mutex. A well-rounded afternoon.) The rule set groups into a few families:

- **Ports and connectors:** direction, matching interfaces, one server per client port, unconnected R-ports.
- **Runnable semantics:** `reads` only on required ports, `writes` only on provided ones, `implicit` only for unqueued data, each RTE event needs the right kind of port.
- **BSW layering:** an upward `uses` is a warning, services reaching into an MCAL driver directly is a hint.
- **OS rules per profile:** AUTOSAR and OSEK have resources and no mutexes; a mutex shared across priorities without a protocol is a priority inversion; `locks A, B` in one task and `locks B, A` in another is a possible deadlock; ISRs never block, category 1 ISRs use no OS objects.
- **Mapping completeness:** each runnable runs in exactly one task, a periodic runnable's period is a multiple of its task's period, exclusive areas are entered by someone.

The command line version (`ardl check`) exits with 1 on errors, so it drops into CI. `ardl render` writes standalone SVGs you can paste into a website. Every diagram in this post came out of it.

## Tasks and ISRs: the OS view

The OS part of the language came from a very practical itch: runnable-to-task mapping is where architecture meets scheduling, and it's where most of my own mistakes live. In ARDL you describe an OS with a profile (`autosar`, `osek`, `threadx`, `freertos`, `generic`) and then its tasks, ISRs and shared objects:

```
os BodyOs profile threadx {
    mutex     NvmLock   protocol inherit
    semaphore AdcSlots  count 2
    queue     LampCmd   of LampState depth 4
    event     PowerDown

    task Task_5ms prio 20 every 5ms
        runs WheelSensor.R_Sample, SpeedCalc.R_Calc
        takes AdcSlots

    task Task_10ms prio 10 every 10ms
        runs LightCtrl.R_Control, ModeManager.R_Main, NvM.NvM_MainFunction
        locks NvmLock
        sends LampCmd

    isr AdcIsr   gives AdcSlots
    isr PowerIsr sets PowerDown
}
```

The OS view draws it: tasks with priority, activation and the runnables mapped into them; ISRs; and the objects they share, each with its own symbol (hexagon for a resource or mutex, pill for a semaphore, a box with slots for a queue, a flag for an event). The edges follow the flow of data and control: sender → queue → receiver, setter → event → waiter, giver → semaphore → taker, and `locks` as a dashed line.

<figure style="margin:1.5rem 0">
<img src="{{ '/assets/images/ardl/body-os.svg' | relative_url }}" alt="OS view: tasks drawn as blue boxes with priority and period, interrupt service routines as red boxes, and shared objects: a semaphore, a queue, an event and a mutex, connected by arrows showing who gives, takes, sends, receives, sets, waits and locks." style="width:100%;max-width:820px;height:auto;display:block;margin:0 auto;border-radius:6px;background:#fff">
<figcaption style="font-size:0.9rem;margin-top:0.5rem">The OS view of the example ECU. You can see at a glance that the ADC ISR feeds <code>Task_5ms</code> through a semaphore, that <code>Task_10ms</code> hands lamp commands to <code>Task_Lamp</code> through a queue, and that two tasks share one mutex.</figcaption>
</figure>

One more thing the OS blocks can do: an OS can be split into several `os` blocks with the same name, in one file or across files. I use that to keep application tasks, BSW scheduling and supervision in separate files, which matches how different people own them. The checks run on the merged OS.

## Working with ARDL: how I start a project

A language is only half of a tool. The other half is the habit around it. This is the workflow I use to get an ECU from "empty folder" to "model the team can review", and the conventions that made it painless.

### 1. Start with a slice, not the whole ECU

I don't model everything first. I pick **one vertical slice**: one signal path from the bus to an actuator, say the wheel speed that ends up in a lamp. That gives me one interface, three or four components, one composition and one task. It's small enough to finish in an hour and big enough to expose the awkward decisions (who owns the data? which task runs it?). Then I widen. Repeated structure doesn't need to be modelled twice: in my multicore example the model describes one QM core and the ASIL core in full and says in the README that the other four QM cores have the same structure and are left out.

### 2. One folder, files by kind (or by feature)

Names are global across the workspace, so there are no imports. Files are just a way to keep humans oriented. Two layouts have worked:

- **By feature:** one file per feature of the ECU (light control, diagnostics, OS). Later files simply use what earlier ones declared. The three examples in the repository do this.
- **By kind:** for a bigger system, interfaces in one file, components per core, the ECU, the BSW and the OS in their own files:

```
model/
  interfaces.ardl        port interfaces and their data types
  swc/
    core1.ardl           QM components of core 1 and their composition
    core0.ardl           ASIL B component of core 0 and its composition
  ecu.ardl               the ECU: both cores and the cross-core channels
  bsw.ardl               BSW modules, main functions, exclusive areas
  os/
    cores.ardl           one OS per core, plus the OS views
    application.ardl     application tasks and the objects of the RTE layer
    bsw-threads.ardl     BSW threads and the cross-core receive path
    safety.ardl          timing protection, memory protection, trusted calls
```

The `os/` files show a trick: an OS can be split into several `os` blocks with the same name, so each concern gets its own file and its own owner (application team, BSW team, safety). The checks run on the merged OS, and views in the first file show it as a whole.

### 3. The order I build things in

1. **Interfaces** first, because everything refers to them.
2. **Components** with ports and runnables, as stubs. Don't write all accesses yet.
3. **Compositions and the ECU**: connectors. The checker immediately tells you about unconnected ports and interface mismatches, which is exactly the conversation you want to have early.
4. **BSW modules** with layers and `uses`. The layers view makes the dependencies visible, and the red arrows are free feedback.
5. **The OS**: tasks, `runs` mappings, shared objects. This is where the checker finds priority inversions, lock-order problems and runnables that nobody maps.
6. **Views** last. Without any `view` declarations a file already shows its compositions, a layers view if it has BSW modules, and each OS part declared in that file. I only add explicit views for the pictures I want to put in a review or a document.

### 4. Conventions that paid off

- **Comments are the trace to the implementation.** I put the file or function that implements a connection in a comment next to it (for example which source file implements a cross-core channel). The model stays readable and `grep` becomes the traceability tool.
- **Mark every guess.** Wherever the design leaves a value open, I write `// assumption:` next to it (a task priority the configuration will decide, say). One `grep -rn "assumption:"` gives the open-decisions list before a review.
- **Write the modelling decisions down.** A README next to the model says what the conventions are: which priority scheme the numbers use, what `every` stands for in this OS, which parts of the real system are deliberately left out. Half of the "is this a bug?" questions in review are answered there.
- **Let the model say less than the truth.** If a detail would force me to invent data, I leave it out. A smaller model that is right beats a bigger one that is decorative.

### 5. The daily loop

1. Edit in VS Code with the preview open beside the editor; fix diagnostics as they appear.
2. Run `ardl check` before pushing. It exits with 1 on errors, so the same command works in CI:

```yaml
- run: |
    git clone --depth 1 https://github.com/Kuebelrobert/ardl /tmp/ardl
    (cd /tmp/ardl && npm ci && npm run build)
    node /tmp/ardl/bin/ardl.cjs check model
    node /tmp/ardl/bin/ardl.cjs render model -o out/diagrams
```

3. Publish the rendered SVGs with the docs, so the diagrams in the wiki are the diagrams of the commit.
4. Review the `.ardl` diff in the pull request. Reviewers who don't want to read the text read the changed diagrams instead.

### 6. Starting from something that already exists

Today there's no importer, so an existing ECU gets modelled by hand, slice by slice. That's less bad than it sounds: writing the slice forces you to read the code or ARXML closely, and the checker reports what you misread. It's also the main reason I want the import described below. A model you have to type in is a model people postpone.

## Pros and cons, without the marketing

| | |
|---|---|
| **Plus** | Text in git: diffs, reviews, blame, branches. |
| **Plus** | Diagrams generated from the model, so never stale. |
| **Plus** | Rules checked in milliseconds, locally and in CI. |
| **Plus** | Small and readable: the grammar is one file, the checker is one file. You can fix a rule you disagree with. |
| **Plus** | The OS view makes runnable-to-task mapping, locks and ISR rules visible. |
| **Minus** | **No ARXML import or export.** The elephant in the room. Today ARDL talks to the outside world through SVG only. (The plan for that is in Part 2.) |
| **Minus** | **No timing model:** no WCET, no schedule simulation, no Gantt chart. That's deliberate (it's what dedicated tools are for), but it means "it checks" never means "it fits". |
| **Minus** | **Global names.** No packages, no imports: every name is declared once across the workspace. Fine for one ECU, awkward for a vehicle. |
| **Minus** | **Data types are names.** There are no ranges, units or conversions. Enough for structure, not for an interface specification. |
| **Minus** | **Classic only.** Adaptive AUTOSAR is a different universe. |
| **Minus** | **My reading of the spec.** The checks encode how I understand the rules. When the specification and ARDL disagree, the specification is right and ARDL has a bug. |
| **Minus** | **Not a qualified tool.** Anything it produces is input for a human, not evidence for an assessor. |
| **Minus** | A one-person project at version 0.3. The install count is a number I can count on my fingers, with fingers to spare. |

If your project already lives in a commercial configuration tool, ARDL won't replace it, and shouldn't. Where it fits is the early phase, the review phase and the "explain this ECU to the new colleague" phase, where a text file beats a tool license and a diagram beats a text file.

## Try it

- **Install:** search for "ARDL" in the VS Code extension view, or take it from the [Marketplace](https://marketplace.visualstudio.com/items?itemName=kuebelrobert.ardl). It's MIT licensed, and the source is [on GitHub](https://github.com/Kuebelrobert/ardl).
- **Open the examples** (light control, diagnostics, OS) and press `Cmd+K V` for the preview.
- **Break something** on purpose and watch the checker. It's the fastest way to learn which rules exist.

In [Part 2]({% post_url 2026-11-06-ardl-part-2-from-model-to-qemu-trace-and-the-import-export-plan %}), the model leaves the editor: it runs on QEMU, produces a trace, and gets a plan for talking to ARXML.
