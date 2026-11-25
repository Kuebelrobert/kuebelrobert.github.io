---
layout: post
title: "CPU, GPU, NPU: How They Work and What an Automotive Architect Should Ask Each of Them"
date: 2026-11-21
categories: [System & SW Architecture]
tags: [cpu, gpu, npu, heterogeneous-compute, central-compute, software-defined-vehicle, determinism, wcet, iso-26262, freedom-from-interference, ai, architecture]
---

<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>mermaid.initialize({ startOnLoad: true, theme: "dark" });</script>

*This post is the groundwork for a two-part series on scheduling. [Part 1]({% post_url 2026-11-21-scheduling-heterogeneous-compute-part-1-gangs-pipelines-and-topology %}) and [Part 2]({% post_url 2026-11-21-scheduling-heterogeneous-compute-part-2-accelerators-budgets-and-orchestration %}) take the three compute units from here and ask how to schedule work across them without losing the safety case.*

> **TL;DR**
>
> - **CPU:** low latency, runs any code, best safety story. Weak at parallel math per watt.
> - **GPU:** high throughput on parallel work and very flexible. Weak on determinism and small jobs, and it comes with a large, opaque driver.
> - **NPU:** the most efficient for neural networks, with a regular execution pattern. Limited to its operator set, and the toolchain isn't yours.
> - No unit wins every requirement. Control loops and safety monitoring stay on lockstep CPU cores, perception goes to the NPU and GPU (with a reserved share if a safety function relies on it), and they meet on one memory path, which is where the timing problems start.

For a long time, "the processor" in an ECU meant one thing: a CPU core, or a few of them, that you knew by heart. Then perception networks arrived, and with them a GPU here, an NPU there, and a datasheet whose block diagram looks like a subway map. Everyone nods when the architecture review says "we run the perception network on the NPU and the rest on the CPU". Fewer people can say what exactly happens when that sentence meets a deadline, a safety goal and a thermal budget.

This post is the groundwork. First, how each of the three actually works, with only as much hardware as an architect needs. Then how they compare against the things automotive cares about, which are not the things the marketing slides care about.

## What's inside

- The three in one table
- How a CPU works, from MCU cores to application cores
- How a GPU works, and why it likes big batches
- How an NPU works, and why it likes exactly one kind of math
- When is an accelerator worth the trip?
- The comparison against automotive requirements
- Where each of them lives in a vehicle
- Questions to ask before you pick one

## The three in one table

| | CPU | GPU | NPU |
|---|---|---|---|
| Built for | Low latency on general, branchy code | High throughput on massively parallel work | High efficiency on neural-network math |
| Parallelism | A few to a few dozen cores | Thousands of lanes in lockstep groups | Dense arrays of multiply-add units |
| Control | Every core fetches its own instructions | One instruction drives a group of lanes | Fixed dataflow, compiled offline |
| Flexibility | Runs anything | Runs anything parallel | Runs a defined set of operators |
| Typical car job | Control loops, safety island, OS, services | Graphics, surround view, flexible compute | Perception networks, driver monitoring |

{% include anim.html src="/assets/videos/scheduling/compute-architectures.mp4" alt="Animation of three panels. The CPU panel shows four cores lighting up independently, each with its own instruction stream. The GPU panel shows rows of small lanes lighting up row by row, then one row where half the lanes wait during a divergent branch. The NPU panel shows a four by four array of multiply-add cells where a wave of data crosses from the left." caption="Three ways to spend transistors. A sketch of the principle, not of any real chip." %}

## How a CPU works

A CPU core is optimized for one thing: finishing *this* piece of sequential code as fast as possible. Big application cores achieve that with a stack of tricks: out-of-order execution, branch prediction, speculation, a deep cache hierarchy and an MMU. Most of the silicon is not arithmetic at all, it's machinery that guesses what the program will do next and keeps the data close.

In automotive, "CPU" covers two very different animals:

- **MCU-class cores** (Cortex-M and Cortex-R style): in-order, short pipelines, tightly coupled memory, an MPU instead of an MMU. Slow by desktop standards, but *predictable*, at least as long as the critical code runs from tightly coupled memory. The larger ones, like the Cortex-M7 of this blog's BCU, also have caches and branch prediction, and need more care. Many of them run in **lockstep**, two cores executing the same code with a hardware comparator, which is the classic way to get high diagnostic coverage for random hardware faults.
- **Application-class cores** (Cortex-A style): out-of-order, large caches, MMU, hypervisor support, running Linux, QNX or similar. Fast, flexible, and much harder to analyze, because the same tricks that make them fast make the worst case difficult to pin down.

**What a CPU is good at:** low latency for small jobs, any kind of control flow, mature tooling (qualified compilers, certified RTOS, debuggers, trace), decades of experience with the safety case. Everything in your safety island is a CPU for a reason.

**What it's bad at:** raw throughput per watt on parallel math. Asking a CPU to run a modern perception network is like asking a very talented accountant to carry bricks.

The catch for architects: even a CPU only gives you determinism as long as you control what it shares. Caches, buses and memory controllers are shared with everyone else on the chip, and Part 1 of the scheduling series will show how quickly that matters.

## How a GPU works

A GPU takes the opposite bet. Instead of a few clever cores, it has a huge number of simple lanes. Lanes are grouped (the groups are called warps, wavefronts or something similar, depending on the vendor), and each group executes **one instruction at a time for all of its lanes**. This model is usually called SIMT, single instruction, multiple threads.

Three consequences matter for system design:

1. **Throughput comes from having a lot of work in flight.** When one group waits for memory, the hardware switches to another one at no cost. That's how a GPU hides memory latency, and it's why it only shines when you feed it thousands of independent work items.
2. **Divergence hurts.** If lanes of one group take different branches, the group runs both paths one after the other, with the other lanes masked off. Branchy code on a GPU is expensive code.
3. **You don't call it, you submit to it.** The CPU prepares data, enqueues kernels through a driver, and the GPU executes them when it gets to them. There's a launch cost, often a data-transfer cost, and a software stack between you and the hardware that you usually don't own.

**What a GPU is good at:** graphics (its origin), surround view, image and point-cloud processing, and running neural networks with maximum flexibility. New network architecture next year? Probably it runs on the GPU. New operator? Write a kernel.

**What it's bad at:** determinism and small jobs. A short job pays the launch and transfer cost and may wait behind someone else's work. Preemption is often coarse (more on that in Part 2), and the driver is a big, complex piece of software that you can't easily put in a safety case. Safety-oriented graphics and compute APIs exist (Vulkan SC is one example), but the ecosystem is far younger than the one for CPUs. Power and heat are the third problem, since a GPU that is busy is a GPU that is hot.

## How an NPU works

An NPU (neural processing unit, or "AI accelerator" if marketing is writing) is what you get when you look at a neural network, notice that most of it is matrix multiplication, and build hardware for exactly that.

The core is an array of multiply-accumulate units, often arranged so that data flows through it in a regular pattern: weights stay in place, activations stream through, partial sums move along. That is the idea behind a systolic array. Next to it sits a lot of on-chip SRAM, so that weights and intermediate results rarely have to travel to DRAM, because moving data costs far more energy than computing on it. Typical arithmetic is low-precision integer (INT8, sometimes lower), which is why networks are **quantized** before deployment.

Two properties define how you work with an NPU:

- **It is compiled, not programmed.** A vendor toolchain takes your trained network and turns it into a static schedule of commands for the array. The execution is typically very regular, which is good news for timing, but the compiler is a black box that decides how your model maps to the hardware.
- **It supports a fixed set of operators.** Convolutions, matrix multiplications and common activations run beautifully. An operator the NPU doesn't know falls back to the CPU or the GPU, which costs time, a data transfer, and sometimes the entire benefit.

**What an NPU is good at:** energy efficiency (the best of the three for the networks it supports), predictable execution time for a given compiled model, small footprint.

**What it's bad at:** anything outside its operator set, and anything that changes faster than the silicon. Network architectures have moved quickly in recent years, and a chip fixed three years before the vehicle ships has to guess which operators will matter. Add the quantization effort and a toolchain you don't control, and "just run it on the NPU" turns into a project of its own.

There's one more point that has nothing to do with hardware. A neural network isn't specified the way classic code is, so the safety argument for it differs. That's the territory of SOTIF and of the work on safety and AI (ISO/PAS 8800 is the recent standard in this area). The accelerator's hardware safety mechanisms are a necessary part of the argument, not all of it.

## When is an accelerator worth the trip?

Every accelerator has a fixed cost before it does any useful work: building the command stream, moving data, waking up, synchronizing the result. The CPU has none of that.

{% include anim.html src="/assets/videos/scheduling/latency-vs-throughput.mp4" alt="Animation of a chart with number of work items on the horizontal axis and time to finish on the vertical axis. The CPU line starts at zero and rises steeply. The GPU line starts higher but is nearly flat. The NPU line starts between them and is nearly flat. The lines cross at small batch sizes, after which the accelerators win." caption="Offsets are launch and transfer costs, slopes are the work itself. Illustrative shapes, not measurements." %}

That's why the same system often runs a small safety-relevant check on the CPU in microseconds while a large perception network runs on the NPU in milliseconds. The crossover point depends on the chip, the model and the memory traffic, so measure it on the target instead of trusting a TOPS number.

## The comparison against automotive requirements

Automotive asks a different set of questions than a benchmark does. Here is the same comparison in the vocabulary of a requirements review. The ratings are relative and general; any specific chip can differ.

| Requirement | CPU (MCU / lockstep) | CPU (application) | GPU | NPU |
|---|---|---|---|---|
| Deterministic timing, bounded WCET | Very good | Moderate (caches, speculation) | Weak (opaque scheduling, shared memory) | Good for a compiled model, if the memory path is isolated |
| Latency for small jobs | Very good | Very good | Weak (launch and transfer) | Moderate |
| Throughput on parallel work | Weak | Moderate | Very good | Very good for supported ops |
| Energy efficiency on neural networks | Weak | Weak | Moderate | Very good |
| Hardware safety mechanisms (lockstep, ECC, BIST) | Very good, mature | Good | Partial, varies a lot | Partial, varies, improving |
| Software stack in a safety case | Mature (qualified tools, certified OS) | Mature but large | Young, large drivers | Young, vendor toolchain |
| Preemption and isolation between criticalities | Well understood | Via hypervisor, MMU | Coarse, partitioning if available | Coarse, mostly by compiled job |
| Flexibility for future workloads | Complete | Complete | High | Limited to the operator set |
| Thermal and power headroom | Excellent | Good | Often the limiting factor | Good |

Reading the table across: no unit wins every row, and the rows where the CPU wins are exactly the ones that appear in safety goals. The rows where the accelerators win are the ones that appear in the feature list. An architect's job is to put each function where its row matters.

## Where each of them lives in a vehicle

On a central or zonal computer, the typical split looks like this:

<div class="mermaid">
flowchart LR
    subgraph SOC["Central compute SoC"]
        direction TB
        subgraph SAFE["Safety island (ASIL)"]
            MCU["Lockstep CPU cores, own SRAM<br/>control loops, monitoring"]
        end
        subgraph APP["Application domain (mixed: QM and ASIL partitions)"]
            ACPU["Application CPU cores<br/>OS, services, fusion logic"]
            GPU["GPU<br/>graphics, surround view,<br/>flexible compute"]
            NPU["NPU<br/>perception networks"]
        end
        MEM["Shared memory + interconnect"]
    end
    MCU --- MEM
    ACPU --- MEM
    GPU --- MEM
    NPU --- MEM
    MCU -. "monitors / supervises" .-> ACPU
</div>

- **Safety island:** lockstep CPU cores with a small, certified software stack. They supervise the rest, run the control and arbitration logic that must always meet its deadline, and decide what happens when something upstream stops responding.
- **Application CPUs:** operating system, middleware, services, fusion logic, everything branchy. They also prepare data for the accelerators, so they set the pace for the whole pipeline.
- **GPU:** anything graphical, plus compute work that is parallel but that you can't commit to an NPU's operator set yet.
- **NPU:** the perception networks you have frozen, where efficiency and a predictable execution time matter.

Don't read "application domain" as "not safety-relevant". If emergency braking relies on camera perception, that perception and the fusion behind it are part of the safety chain, and need a reserved, argued share of the NPU and the CPU. The comfort functions next to them don't.

The safety island keeps its critical code and data in its own memory, but it still exchanges data over the interconnect, and the other three share the main memory all the time. That picture is why the two scheduling posts exist.

## Questions to ask before you pick one

If you only take a list away from this post, make it this one. Ask the vendor and your own team:

- **Operators:** which operators does the NPU support natively, and what falls back to where? What does a fallback cost in time and data movement?
- **Timing:** what is the execution time of a compiled model, and what's its spread? What shares the memory path while it runs?
- **Preemption:** at which granularity can a running job be interrupted on the GPU and the NPU? Who has priority, and who arbitrates?
- **Isolation:** how do you prevent a QM workload from slowing a safety function, in time (bandwidth, cache) and in space (memory protection)?
- **Safety mechanisms:** which diagnostics exist for the accelerator (ECC, BIST, monitoring), and which safety manual describes their coverage?
- **Software stack:** who delivers the driver and the compiler, with which qualification, and how are updates handled?
- **Model lifecycle:** how often will the model change, and what does a change cost (requantization, requalification, retiming)?
- **Power and thermal:** what happens at the thermal limit? Does throttling silently change your timing?

## Wrap-up

The CPU gives you latency, flexibility and the best safety story. The GPU gives you throughput and flexibility, at the price of determinism. The NPU gives you efficiency and a regular execution pattern, at the price of flexibility and a toolchain you don't own. A modern vehicle computer uses all three, because no single one fits every row of the requirements table.

Which leaves the real question: once all three are on the same chip and share the same memory, who decides what runs where and when, and how do you prove that the decision never breaks a deadline? That's what the next two posts are about. [Part 1]({% post_url 2026-11-21-scheduling-heterogeneous-compute-part-1-gangs-pipelines-and-topology %}) starts with the scheduling toolbox of machine-learning clusters and what survives the trip into a car.
