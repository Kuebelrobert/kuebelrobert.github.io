---
layout: post
title: "Scheduling Like a GPU Cluster, Certifying Like a Brake Controller, Part 2: Accelerators, Budgets and Orchestration"
date: 2026-11-21
categories: [RTOS]
tags: [scheduling, preemption, mixed-criticality, budgets, batching, orchestration, software-defined-vehicle, slo, gpu, npu, autosar-adaptive, iso-26262, architecture]
---

<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>mermaid.initialize({ startOnLoad: true, theme: "dark" });</script>

*This is part 2 of a two-part series. [Part 1]({% post_url 2026-11-21-scheduling-heterogeneous-compute-part-1-gangs-pipelines-and-topology %}) covered the objective functions, gang scheduling and topology-aware placement. The groundwork on the three compute units is in [CPU, GPU, NPU]({% post_url 2026-11-21-cpu-gpu-npu-who-computes-what-in-the-vehicle %}).*

> **TL;DR**
>
> - **Preemption on accelerators:** bound the wait, not the average. Split long jobs into bounded work units or partition the hardware.
> - **Batching:** in a car the batch size follows from the sensor set. Keep the latency arithmetic, drop the dynamics.
> - **Dynamic scheduling** belongs in the QM domain and the slack. Safety budgets are reserved and fixed per mode, ideally identical in every mode, and the mode switch itself is analyzed.
> - **Orchestration** fits the service domain. An SLO is not a deadline, so cut the runtime freedom at the safety boundary. The cluster playbook fits the development infrastructure around the car almost unchanged.

Part 1 ended with a placement that respects the topology. Now the hardest question: the system is running, and something with a deadline needs the accelerator that a long job currently owns. On a CPU, that's a solved problem with a thick textbook. On an accelerator, it is a negotiation with a driver.

This post covers the remaining techniques from the ML-infrastructure toolbox: preemption, batching, dynamic workload scheduling and orchestration. For each one, what it means in a car, and where the fence has to go.

## What's inside

- Preemption: easy on the CPU, a negotiation everywhere else
- Batching: when the batch size is chosen by the sensor set
- Dynamic workload scheduling, with budgets and a fence
- Orchestration and SLOs versus deadlines
- Development infrastructure: where the cluster playbook fits as it is
- Takeaways and a checklist

## Preemption: easy on the CPU, a negotiation everywhere else

On a CPU, preemption is old news. A 1 ms control task preempts a 100 ms diagnostic task, the cost of the context switch is known and bounded, and the effects of priority inversion are understood and contained by priority ceiling protocols (AUTOSAR resources are exactly that). You can write the whole thing into a response-time analysis and move on with your life.

Now put a long neural-network job on a GPU or an NPU and let a safety function ask for the same hardware.

- **Granularity.** Many accelerators can only switch between jobs at coarse boundaries: the end of a kernel, a command buffer, a layer, a whole compiled network. Fine-grained preemption exists on some GPUs and is much rarer on NPUs.
- **Cost.** Saving the state of thousands of lanes or a systolic array and its on-chip SRAM is not a register dump. It can take real time, and it isn't free in energy either.
- **Opacity.** The scheduler sits in a driver or firmware you usually can't read, let alone analyze.
- **Arbitration.** If two clients submit work, who decides, by which policy, with what bound on the wait?

The thing to bound is the time between "the safety job is ready" and "the safety job starts running". That wait is the blocking term of your analysis, and with a non-preemptible kernel, it's as long as the kernel.

{% include anim.html src="/assets/videos/scheduling/accelerator-preemption.mp4" alt="Animation with three rows on a time axis. Row one: a 40 millisecond QM kernel runs without preemption; a safety job requested at 2 milliseconds waits 38 milliseconds and misses its 15 millisecond deadline. Row two: the QM work is split into 5 millisecond slices; the safety job starts at the next slice boundary and meets the deadline. Row three: the safety job runs on its own reserved slice immediately, while the QM job runs longer on the remaining slice." caption="Three ways to deal with a safety job on a busy accelerator. Numbers are illustrative." %}

In practice there are three families of answers, and the animation shows them:

1. **Do nothing.** Accept the long wait and make sure it fits the deadline. Fine if your safety job has a generous deadline and the QM kernels are short. A gamble otherwise.
2. **Bound the work units.** Split long jobs into small, bounded chunks (smaller kernels, layer-wise submission, tiled execution, per-slice time budgets) so that the maximum non-preemptible section is short and known. The price is some overhead and more software complexity, and utilization stays high. This is the closest relative of how you treat long critical sections on a CPU.
3. **Partition the hardware.** Give the safety function its own slice: a dedicated engine, a hardware partition of the accelerator if the chip offers one, or a reserved time window on the device. The safety job then starts immediately, and the QM job pays in utilization. It's only independent if the path to memory is partitioned too: an engine of its own behind a shared memory controller is [placed apart, not isolated]({% post_url 2026-11-21-scheduling-heterogeneous-compute-part-1-gangs-pipelines-and-topology %}#topology-aware-placement-the-most-useful-import). With that covered, this is the easiest argument for a safety case and the most expensive one in silicon use.

Whichever you choose, there are two quiet traps:

- **Power management is a scheduler too.** Frequency scaling and thermal throttling change execution time without asking you. A WCET measured at full clock under a cool lab bench is a nice number, and not necessarily the number at 85 °C in July.
- **The first run isn't the typical run.** Warm-up effects, memory allocation, shader or kernel compilation and cold caches make the first execution slower. Design them out, or budget for them.

## Batching: when the batch size is chosen by the sensor set

In a data center, dynamic batching is a classic trick: collect requests for a few milliseconds, run them together, trade a bit of latency for a lot of throughput. The batch size follows the traffic, and the scheduler's job is tuning that trade-off.

In a vehicle, the situation is different:

- The "traffic" is not random. It's a fixed set of sensors with fixed rates. Six cameras at 30 Hz is a perfectly predictable load.
- The batch is therefore **a design decision**: you may process the six camera images as one batch of six, because they are triggered in the same cycle (on a [common clock]({% post_url 2026-11-24-automotive-ethernet-for-the-sdv-part-3-time-tsn-and-security %}#why-a-vehicle-needs-one-clock)), and the batch size never changes.
- Waiting to fill a batch costs latency, and in a safety path that latency has to be in the budget. Waiting is only acceptable if the wait is bounded and counted.

So, the useful import isn't the dynamic part, it's the **arithmetic**: latency is the time to collect the batch plus the execution time of the whole batch, and the throughput gain has to pay for that. Make the batch size a configuration parameter with an analysis behind it, not a runtime heuristic.

## Dynamic workload scheduling, with budgets and a fence

Now the tempting one. A central computer hosts perception, parking functions, infotainment, voice, navigation, diagnostics and updates. Not all of them are needed all the time, and the car knows which mode it's in. A scheduler that moves resources to where they're useful is attractive, because it can be the difference between sizing the hardware for the sum of all functions and sizing it for the worst *simultaneous* case.

{% include anim.html src="/assets/videos/scheduling/budget-modes.mp4" alt="Animation of a stacked bar showing the share of compute capacity per domain. In highway driving, perception takes the largest QM share. In parking, surround view takes the largest share and perception shrinks. At standstill, diagnostics and updates take the largest share. The safety functions segment at the bottom stays the same height in every mode and is marked as guaranteed. A note says a mode switch is a worst case too." caption="The safety budget stays put. Only the QM domain follows the driving mode. Perception in the QM share means comfort functions; perception that emergency braking relies on belongs to the safety segment. Illustrative numbers." %}

| Situation | Scheduling strategy |
|---|---|
| Highway driving | More compute for comfort perception and prediction |
| Parking | More for surround view and short-range sensing |
| Standstill, charging | Background diagnostics, logging, updates |
| Critical situation | Change nothing for safety, at most stop QM work to save power and heat |

The rule that makes this certifiable, and I'm going to say it plainly: **safety functions must never depend on an unpredictable dynamic allocation.** They get a reserved budget (cores, accelerator slice, memory bandwidth, time windows) at design time, and the simplest rule is that this budget is the same in every mode. If that would oversize the hardware, because emergency braking and automated parking never run at full load together, use a small set of analyzed modes, each with fixed safety budgets and with an analyzed transition. What you don't do is renegotiate in the critical moment, since a mode switch right then would be the worst case in the worst place. The dynamic part lives *inside* the QM domain and in the slack, and it's never allowed to take something back from the budgets above it.

Three things are easy to forget:

1. **The mode switch is a worst case, too.** When the car goes from driving to parking, resources are released from one function and acquired by another. When exactly is the old budget free, and from which moment can the new function rely on it? A transition that is not analyzed is where the surprises live.
2. **Slack is not a budget.** Using idle time of a safety budget for QM work is fine (this is slack reclamation, a well-known technique), as long as it can be taken back instantly and with a bounded delay. If "taking back" requires the QM job's cooperation, it isn't taken back.
3. **Degradation is a design item.** What does the QM function do when its budget shrinks to zero? Graceful degradation, a defined fallback, or a reset: pick it on purpose.

The research field for all of this is called **mixed-criticality scheduling**: running functions of different criticality on shared hardware while keeping the guarantees of the critical ones. In practice, the enforcement comes from the hypervisor or the OS (time and space partitioning, budgets with timing protection), and the policy on top is the thing you'd call the "dynamic scheduler".

On the AUTOSAR Adaptive side, the corresponding concepts are execution management and state management with function groups: you define which applications run in which machine state, and the platform starts and stops them accordingly. That's a mode-aware policy, with the right granularity, which is why it's the natural place to attach the resource budgets from above.

## Orchestration and SLOs versus deadlines

The other half of the job description was Kubernetes: operators, custom resources, controllers that reconcile desired and actual state. The idea in one sentence: describe what you want declaratively, and a control loop makes it so, again and again, when things fail.

For a software-defined vehicle, the attraction is obvious. Applications are updated independently, deployed as containers, restarted on failure, and described by manifests: *this service needs two cores, an NPU slice, 2 GB of memory, and talks to these others.* That's a good model for the non-critical side of the vehicle. It brings tooling, repeatability and a way to manage many services across several compute partitions.

The mismatch is in the semantics:

| | SLO (cluster world) | Deadline (safety world) |
|---|---|---|
| Statement | "99.9 % of requests under 50 ms" | "Always under 50 ms" |
| Violation | Budget burned, alert, maybe an apology | Hazard, possibly a recall |
| Recovery | Restart, reschedule, retry | A defined safe state within a time bound |
| Evidence | Monitoring over time | Analysis before release |

An SLO accepts that things will occasionally go wrong, and optimizes the *rate*. A deadline accepts nothing, and demands proof. Both are legitimate, they just belong in different places.

So the dividing line I'd draw:

- **Orchestration in the QM/service domain:** infotainment, navigation, cloud-connected services, non-critical perception add-ons, diagnostics services. A restart is acceptable, a declarative control loop is welcome.
- **Static, analyzed allocation in the safety domain:** control and arbitration, safety monitors, anything with a hard deadline. The orchestrator may *start* these as part of a defined state, but it doesn't *place or resize* them at runtime.
- **A narrow, well-defined interface in between:** the orchestrator requests resources from the pool that the safety domain has *left over*, never the other way around.

If you like the pattern, the transferable part is the declarative resource description, a manifest that states criticality, budget and interference constraints in a form that a tool can check. The controller that moves things around at runtime is the part you cut down to what the safety case can bear.

## Development infrastructure: where the cluster playbook fits as it is

One place where you can import almost everything unchanged: the infrastructure *around* the car.

- Simulation and virtual ECUs in large numbers, SIL test pipelines, regression runs per commit.
- Training and validation of perception models.
- Hardware-in-the-loop benches, which are scarce, expensive and shared, a perfect case for queues, reservations and priorities.
- Data processing for recorded drives.

Here, gang scheduling (multi-GPU training, parallel simulation with synchronized steps), bin-packing, preemption of low-priority jobs and plain old fair-share queues are exactly the right tools. Nobody dies if the nightly regression runs late, and the cluster people have been solving this for years. Borrow shamelessly.

## Takeaways

- **Preemption on accelerators** is the open problem. Expect to solve it by bounding work units or partitioning the hardware, not by clever dynamic arbitration, and bound the *wait*, not the average.
- **Batching** in a car is a design parameter set by the sensor configuration. Keep the arithmetic, drop the dynamics.
- **Dynamic scheduling** is fine inside the QM domain and the slack. Safety budgets are reserved and fixed per mode, ideally identical in every mode, and the mode switch is analyzed.
- **Orchestration** fits the service domain well. SLOs and deadlines are different promises, so keep the declarative model and cut the runtime freedom at the safety boundary.
- **The infrastructure around the car** can take the cluster playbook almost unchanged.

The architect of a modern vehicle platform doesn't only draw software structures anymore. They own how compute is distributed, isolated and orchestrated, and that sits between embedded engineering, operating systems and AI infrastructure. Possibly the most honest sentence in this entire series: nobody has the final answer yet, and the people who learn both vocabularies will be the ones writing it.

## Checklist

- [ ] Safety budgets (cores, accelerator slice, memory bandwidth, time windows) reserved at design time, fixed per mode and ideally identical in every mode
- [ ] Maximum non-preemptible section on every accelerator known and included in the blocking term
- [ ] Preemption strategy chosen per accelerator: bounded work units, partitioning or accepted wait, with evidence
- [ ] WCET measured under adversarial load, thermal limits and power-management states included
- [ ] Batch size fixed by configuration, with the latency arithmetic documented
- [ ] Mode switches analyzed: release and acquisition of budgets, with bounded delays
- [ ] Slack reclamation revocable with a bounded delay and without the QM job's cooperation
- [ ] Degradation behavior of every QM function defined for a budget of zero
- [ ] Orchestration limited to the QM/service domain, with a narrow interface to the safety domain
- [ ] Monitoring that detects when an analysis assumption no longer holds

## Further reading

- S. Vestal: *Preemptive Scheduling of Multi-Criticality Systems with Varying Degrees of Execution Time Assurance* (2007), the paper that started the mixed-criticality field.
- A. Burns, R. Davis: *Mixed Criticality Systems: A Review*, a survey that is regularly updated.
- ISO 26262-6, Annex D, on freedom from interference, and ISO/PAS 8800 on safety and AI for road vehicles.
- AUTOSAR Adaptive Platform: specifications for Execution Management and State Management.
