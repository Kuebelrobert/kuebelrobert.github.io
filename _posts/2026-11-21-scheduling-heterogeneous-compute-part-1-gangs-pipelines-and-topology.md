---
layout: post
title: "Scheduling Like a GPU Cluster, Certifying Like a Brake Controller, Part 1: Gangs, Pipelines and Topology"
date: 2026-11-21
categories: [RTOS]
tags: [scheduling, gang-scheduling, topology-aware-placement, mixed-criticality, heterogeneous-compute, response-time-analysis, freedom-from-interference, iso-26262, cache-partitioning, architecture]
---

<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>mermaid.initialize({ startOnLoad: true, theme: "dark" });</script>

*This is part 1 of a two-part series. It builds on [CPU, GPU, NPU]({% post_url 2026-11-21-cpu-gpu-npu-who-computes-what-in-the-vehicle %}), which explains the three compute units. [Part 2]({% post_url 2026-11-21-scheduling-heterogeneous-compute-part-2-accelerators-budgets-and-orchestration %}) covers accelerators, budgets and orchestration.*

> **TL;DR**
>
> - Cluster schedulers maximize utilization, automotive schedulers guarantee deadlines. The mechanisms transfer, the objective doesn't.
> - **Gang scheduling** means all threads of one job run together. A sensor pipeline is not an example of it, that's a data-dependency problem. In a car, a static schedule gives you gang scheduling without a runtime mechanism, paid for at design time.
> - **Topology awareness** is the most valuable import: placed apart is not isolated. Shared cache, interconnect and memory controller break your timing analysis, so partition them where the silicon allows.
> - In automotive, the "scheduler" is often a generator in the build, and the runtime only enforces its decisions.

I recently read a job description for scheduling workloads on large GPU clusters: gang scheduling, topology-aware placement, preemption, batching, operators, SLOs. Not one automotive word in it. And yet I kept nodding, the way you nod when a stranger describes your own problems in a foreign accent.

Every one of these problems exists on a modern central vehicle computer. The difference is the price of getting it wrong. In a cluster, a bad scheduling decision burns money. In a car, it burns the safety case. This series is about which ideas survive the trip, and what you have to bolt on so that they do.

## What's inside

- Two worlds, two objective functions
- A quick refresher on how automotive schedules today
- Gang scheduling: what it is, and what it is not
- Topology-aware placement: the most useful import
- Placement as a build step, not a runtime service
- Takeaways

## Two worlds, two objective functions

The same word, "scheduling", optimizes opposite things.

| | ML infrastructure | Automotive embedded |
|---|---|---|
| Goal | Keep expensive hardware busy | Meet every deadline, always |
| Metric | Utilization, throughput, percentile latency | Worst-case response time |
| Load | Elastic, unpredictable | Bounded, analyzed up front |
| Failure | Job restarts, SLO burn, an angry dashboard | Hazard, a finding in the safety audit |
| Proof | Monitoring and charts | Analysis and freedom from interference |

A cluster scheduler is happy at 95 % utilization. An automotive scheduler would regard 95 % utilization as a confession. It's happy when the safety function meets its deadline at maximum system load, in the worst case, provably. Everything below follows from that difference, and each technique has to be checked against it.

## A quick refresher: how automotive schedules today

Before importing anything, remember what is already in the toolbox, because a lot of it is good.

- **Fixed-priority preemptive scheduling.** The classic AUTOSAR OS (and of most RTOSes in the field) model. Priorities are assigned at design time, the highest ready task runs.
- **Response-time analysis.** With priorities fixed and execution times bounded, the worst-case response time of task *i* is the fixed point of

  `R_i = C_i + B_i + Σ_j ceil(R_i / T_j) · C_j`

  where `C` is the worst-case execution time, `B` the blocking by lower priorities (resources, non-preemptible sections), and the sum runs over all higher-priority tasks `j` with period `T_j`. If `R_i ≤ D_i` for every task, you have a proof instead of a feeling. It's a proof under assumptions: deadlines not longer than periods, independent tasks, no release jitter, and a `C` that really bounds the execution time. Extensions of the formula cover jitter and longer deadlines; the last assumption is the one this post is about.
- **Time-triggered execution.** Schedule tables or time-partitioned windows, fixed at configuration time. Boring, and therefore certifiable.
- **Timing protection.** The OS enforces execution budgets and inter-arrival times, so that one misbehaving task can't eat everybody else's time.
- **Static multi-core partitioning.** Tasks and software components are allocated to cores at design time, as in the [foundation series]({% post_url 2026-10-19-create-the-foundation-part-4-swc-allocation-and-task-setup %}).

Notice the pattern: the answer to "where and when does this run?" is *decided before the car starts*. That is not a lack of imagination, it is the whole point. Keep it in mind for the rest of the post.

## Gang scheduling: what it is, and what it is not

**The idea.** A parallel job consists of several threads that need to meet regularly, at a barrier or in a collective operation. If one thread is descheduled while the others wait, they all sit idle until it comes back. Gang scheduling (also called co-scheduling) avoids that by giving *all* threads of a job their time slice at the same moment, on different cores. It's a very old idea, and it's what keeps hundreds of accelerators from waiting for the one that got preempted.

{% include anim.html src="/assets/videos/scheduling/gang-vs-pipeline.mp4" alt="Animation with three stages. First, four threads of job A on four cores reach a barrier, but one thread was preempted by job B, so the other three cores show a red waiting segment. Second, with gang scheduling all four threads of job A run at the same time, reach the barrier together, and job B runs afterwards. Third, a sensor pipeline with camera, radar and lidar preprocessing feeding sensor fusion, labeled as a data dependency problem rather than a gang scheduling problem." caption="One after the other: an uncoordinated barrier, the same job with gang scheduling, and a sensor pipeline, which is a different problem." %}

**What it is not.** Here is where I want to correct a common example. The usual automotive illustration for gang scheduling is the sensor pipeline: camera preprocessing on one core, radar on another, lidar on a third, fusion on the GPU. It sounds right, but it's a different problem. That is a *pipeline with data dependencies*. The fusion stage doesn't need the three preprocessing stages to run *at the same moment*, it needs their results to **belong together**: same time base, same cycle. You solve that with timestamps on a [common clock]({% post_url 2026-11-24-automotive-ethernet-for-the-sdv-part-3-time-tsn-and-security %}#why-a-vehicle-needs-one-clock), synchronized triggers, a static schedule, or a buffer that picks matching samples. Nobody needs to co-schedule anything.

**Where it does apply.** Threads that really rendezvous: data-parallel work split across cores with barriers in between, or a single function spread over several cores or accelerators that exchange data every iteration. Think of a large model split over several compute units, or a parallel image-processing stage. There, a descheduled participant stalls the whole group.

**What automotive does instead.** In hard real-time systems you rarely need a dynamic gang scheduler, because you already control the schedule. A time-partitioned window or a schedule table that runs all participants at the same offset *is* gang scheduling, paid for at design time and with the worst case known. An ARINC-653-style major frame with partition windows works the same way, provided the windows are aligned across the cores.

**The price.** Gang scheduling has a famous weakness: *fragmentation*. If a gang needs four cores and only three are free, the three sit idle, unless the scheduler backfills them with smaller jobs. In a cluster, backfilling is a refinement. In a vehicle it's a risk, because backfilled work has to be preemptible without a trace, or you have just invented an interference channel.

So: take the concept (explicit co-scheduling constraints, expressed as data), not necessarily the algorithm.

## Topology-aware placement: the most useful import

If I had to bet on one technique from the ML world, this would be it.

A topology-aware scheduler doesn't see "N cores and M GB". It sees the hardware as a graph:

- Which core sits in which cluster?
- Which memory does it reach, at what latency?
- Who shares a cache level?
- Which interconnect link carries which traffic?
- Which cores are close to which accelerator?

In an ML cluster, this decides whether two GPUs talk over a fast link or a slow one. On a heterogeneous vehicle SoC, it decides whether your timing analysis is true.

**Placed apart is not isolated.** The textbook picture says: put the time-critical control task on a dedicated core, run the heavy neural network on the NPU, done. Then reality shows up. Both still share the cache hierarchy, the interconnect and the memory controller. The moment the NPU streams a feature map through memory, your control task, which hasn't changed a single instruction, waits.

{% include anim.html src="/assets/videos/scheduling/shared-resource-interference.mp4" alt="Animation of a block diagram with a control core and an NPU cluster both connected to a shared cache and interconnect, then to a memory controller and DRAM. Below, three runs of the control task: alone it takes 0.7 milliseconds; with the NPU busy, a red segment shows waiting on memory and the deadline is missed; with cache partitioning and a bandwidth cap, a small amber extension shows the task slower than alone but still within the deadline." caption="Same core, same code, three runs. Only the neighbour changes. Numbers are illustrative." %}

This is the single biggest practical problem of multi-core and heterogeneous safety systems: the **freedom-from-interference** argument of ISO 26262 doesn't stop at the core boundary. It covers temporal interference (shared bandwidth, shared caches, shared bus arbitration), spatial interference (memory protection) and communication. Aviation hit the same wall earlier and produced dedicated guidance for multi-core interference, so you're in good company.

**What topology awareness gives you:**

1. **Placement that respects the shared resources.** Put things that interfere far apart, and things that must communicate close together.
2. **A model to analyze.** If your placement tool knows that two cores share an L2 cache, it can account for that in the timing budget.
3. **A place to attach mitigations.** Where the hardware offers them, you turn "placed apart" into "isolated": cache partitioning (way-based or colored), memory bandwidth regulation per core or per master, per-master QoS at the interconnect, MPU/SMMU rules for spatial isolation. Availability varies a lot between SoCs, and *how* they're offered (hardware, hypervisor, driver) matters for the safety case.

**What to check on a given chip:**

- Can the shared cache levels be partitioned?
- Can memory bandwidth be limited per master (including the accelerators)?
- Is there an arbitration or QoS configuration at the interconnect, and does it apply to the accelerators too?
- Is every accelerator behind an SMMU/IOMMU, so that a faulty job can't corrupt the memory of another domain?

If the answers to the first three are "no", then the worst-case execution time of a core that shares memory with a busy accelerator is a number you have to measure under adversarial load and add a margin to, and it's wise to be honest about how large that margin is. If the fourth is "no" as well, timing is your smaller problem.

## Placement as a build step, not a runtime service

In the cluster world, the scheduler is a service: it receives requests, scores the nodes, and places a job in milliseconds. In safety-relevant automotive software, the interesting version runs **in your build**.

The logic is the same, only the time of execution changes. You describe the hardware topology as data, the workload requirements as data (criticality, period, WCET estimate, memory footprint, preferred accelerator, who it talks to), and a generator produces the static allocation plus the evidence. A sketch of what the "scheduler" looks like:

```python
# Greedy placement at configuration time (sketch). A real tool uses a constraint solver,
# because greedy can paint itself into a corner that a different order would have avoided.
for task in sorted(tasks, key=lambda t: (-t.criticality, t.period)):
    candidates = [c for c in cores if c.cluster.domain in (None, task.criticality)]
    candidates = [c for c in candidates if fits_budget(c, task)]          # utilization + response time
    candidates = [c for c in candidates
                  if not shares_unpartitioned_resource(c, task, placed)]  # interference rule
    if not candidates:
        raise Infeasible(task)                                              # fail the build, don't guess
    best = min(candidates, key=lambda c: comm_cost(c, task, placed))      # keep talkers close
    best.cluster.domain = task.criticality                                # cluster now belongs to it
    placed[task] = best
```

Two rules do most of the work: *never share an unpartitioned resource between criticalities*, and *keep communicating tasks close*. The rest is bookkeeping, which is exactly what a tool should be doing instead of an architect with a spreadsheet and optimism.

The runtime part stays small and boring: the OS or hypervisor enforces what the build decided (budgets, partitions, memory protection), and monitors that the assumptions hold.

## Takeaways

- The *mechanisms* of cluster scheduling transfer. The *objective* doesn't: throughput on one side, guaranteed deadlines on the other.
- **Gang scheduling** is a real concept for tightly coupled parallel work, but a sensor pipeline isn't an example of it. In automotive you usually get it from a static schedule, paid for at design time.
- **Topology awareness** is the most valuable import, because interference through shared resources is what breaks timing analysis on modern SoCs. Placed apart is not isolated.
- In automotive, the "scheduler" is often a **generator in the build**, backed by a small runtime that enforces its decisions.

That covers the CPU-shaped half of the story. What happens when the thing you want to preempt is an accelerator, when the load changes with the driving situation, and when somebody suggests a container orchestrator for the car? That's [Part 2]({% post_url 2026-11-21-scheduling-heterogeneous-compute-part-2-accelerators-budgets-and-orchestration %}).

## Further reading

- C. L. Liu, J. W. Layland: *Scheduling Algorithms for Multiprogramming in a Hard-Real-Time Environment* (1973), the origin of rate-monotonic analysis.
- J. K. Ousterhout: *Scheduling Techniques for Concurrent Systems* (1982), the paper that introduced co-scheduling.
- H. Yun et al.: *MemGuard: Memory Bandwidth Reservation System for Efficient Performance Isolation in Multi-core Platforms* (2013), per-core bandwidth regulation as a research prototype.
- ISO 26262-6, Annex D, on freedom from interference between software elements.
