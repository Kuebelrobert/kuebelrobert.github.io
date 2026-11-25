---
layout: post
title: "Automotive Ethernet for the SDV, Part 3: Time, TSN and Security"
date: 2026-11-24
categories: [Communication]
tags: [communication, automotive-ethernet, software-defined-vehicle, gptp, tsn, qos, time-synchronization, sensor-fusion, macsec, secoc, security, architecture]
---

*This is Part 3 of a three-part post on how Ethernet works inside a software-defined vehicle. [Part 1]({% post_url 2026-11-24-automotive-ethernet-for-the-sdv-part-1-architectures-frames-and-switches %}) covered the vehicle architectures, frames and switches; [Part 2]({% post_url 2026-11-24-automotive-ethernet-for-the-sdv-part-2-addresses-services-and-diagnostics %}) covered addresses, services and diagnostics; this part covers time, TSN and security, and maps everything back to the architectures.*

> **TL;DR**
>
> - Sensor fusion needs one clock. gPTP measures the delay of every link and corrects for it, down to well below a microsecond with hardware timestamps.
> - Half of a path's asymmetry becomes a time error. Below the 800 ns limit, no ECU reports it.
> - In a vehicle, the grandmaster is configured, not elected. On loss, hold over on the own clock, and declare the time invalid when the drift gets too large.
> - Use the simplest QoS tool that meets the requirement: priority first, a shaper for streams, preemption against long frames, time windows only for fixed slots.
> - A tight TSN schedule and over-the-air functions pull in opposite directions. Leave room in the windows.
> - Switch learning, ARP, service discovery and gPTP believe whoever speaks. Configure statically, segment, then add cryptography.

After [Part 1]({% post_url 2026-11-24-automotive-ethernet-for-the-sdv-part-1-architectures-frames-and-switches %}) and [Part 2]({% post_url 2026-11-24-automotive-ethernet-for-the-sdv-part-2-addresses-services-and-diagnostics %}), our four functions (emergency braking, brake light, surround sound with reversing camera, updates with diagnostics) can reach each other. Two things are missing. The AEB fusion can't combine a camera and a radar that disagree about the time. And nothing so far stops an update from delaying a brake request, or a stranger from sending one.

Most of this part happens on layer 2, below IP; the [OSI map in Part 1]({% post_url 2026-11-24-automotive-ethernet-for-the-sdv-part-1-architectures-frames-and-switches %}#the-map-osi-layers-in-the-vehicle) shows where each piece sits.

## What's inside

- Why a vehicle needs one clock
- gPTP: measure the path, then set the clock, across switches
- What the measurement can't see, and who is the grandmaster
- QoS and TSN, applied to the four functions
- Security: a network that believes everything
- All pieces mapped to the four architectures, and review questions

gPTP and TSN numbers from the lab exercises are calculated or expected from the configuration, not my measurements.

## Why a vehicle needs one clock

**The analogy.** Two dashcams record the same accident, and one of them runs ten seconds slow. Each video is correct. Together, they show two different accidents.

**In detail.** The camera sees a pedestrian at 12.0 m, the radar an object at 11.4 m. Is that the same one? At 50 km/h, the car moves 1.4 cm in a millisecond. Clocks that differ by 10 ms put 14 cm of error into the position, and the estimated speed is off as well. To explain the whole 60 cm, the clocks would have to be 43 ms apart. With a common clock you can rule that out, and what remains is measurement noise or a second object. Without it, you can't tell.

| Vehicle function | Why it needs common time | Order of magnitude needed |
|---|---|---|
| Sensor fusion for AEB and lane keeping | Combine measurements of different sensors | Below 1 ms |
| Surround sound | Speakers on different amplifiers play in sync | Some µs to some tens of µs |
| TSN schedules | All switches open their windows together | Around 1 µs |
| Event data, DTC timestamps, logs | Put events of different ECUs in order | Milliseconds |

The values are orders of magnitude, so derive yours from speed and tolerated error. gPTP is usually better than 1 µs over a few hops. It's the schedule that needs this, not the fusion.

## gPTP: measure the path, then set the clock

**The analogy.** A rally office sends its time to a service point by courier: "It was exactly noon when the courier left." That helps only if you know the driving time. So you first send a courier there and back, and have the other side note how long the stop took. Total time minus the stop, divided by two, is one way. It works even if both clocks are wrong, because each side only measures *durations* on its own clock.

**In detail.** gPTP (generalized Precision Time Protocol, IEEE 802.1AS) runs directly on Ethernet, to an address (`01:80:c2:00:00:0e`) that a switch doesn't forward. It has two parts:

- **Peer delay.** Every port measures the delay to its direct neighbor with four timestamps: `delay = ((t4 - t1) - (t3 - t2)) / 2`.
- **Sync and Follow_Up.** The master sends Sync, and in a second message the exact time at which Sync left, which it can only know afterwards. The lab configuration does this eight times per second.

{% include anim.html src="/assets/videos/automotive-ethernet/gptp-sync.mp4" alt="Sequence animation with numbers: the camera sends Pdelay_Req at t1 = 100, the gateway receives it at t2 = 5125, answers at t3 = 5525, and the camera receives the answer at t4 = 550. The delay is 450 minus 400, divided by two, 25 nanoseconds. Then the gateway sends Sync at 10000, the camera receives it at 5025 on its own clock. 5025 minus 10000 minus 25 gives minus 5000 nanoseconds." caption="The camera is 5 µs behind. The delay measurement is correct anyway, because the offset cancels out." %}

The timestamps have to be taken in hardware, in the PHY or MAC, at the moment the frame enters the wire. With the software timestamps of the lab, a virtual "cable" can be expected to look about 20 µs long, with an offset that jitters by some microseconds. A real 5 m cable in a car takes about 25 ns. So "supports IEEE 1588 timestamping" belongs in the requirements for the MCU, the PHY and the switch, before the hardware is chosen.

### Across the switches of the vehicle

**The analogy.** A relay with a stopwatch on the baton. Every runner adds their own time, so the last one knows the total.

**In detail.** Between the grandmaster in the central computer and a camera in the front bumper there may be two or three switches, and each can hold a frame for an unpredictable time. So every switch takes part. It receives the time on one port, adds how long the information stayed inside (*residence time*) and the delay of the incoming link, and sends a Sync of its own on the other ports. The sum travels in the `correctionField`, with two-step operation in the Follow_Up message.

{% include anim.html src="/assets/videos/automotive-ethernet/gptp-bridges.mp4" alt="Animation: a Sync travels from the gateway over switch A and switch B to the camera. The correction grows from 25 to 2025, 2055, 5055 and finally 5075 nanoseconds, as link delays and residence times are added." caption="Links are drawn larger than they are. Most of the time is spent inside the switches." %}

### What the measurement can't see

Dividing by two assumes that both directions take equally long. Add 2 ms of extra delay in one direction, as the lab exercise does, and the calculated delay rises by 1 ms, and the clock offset is off by 1 ms, even if both clocks are identical. **Half of the asymmetry becomes error.** The lab only accepts this link because its limit for the measured delay was raised to 10 ms, since virtual links are slow. With the usual limit of 800 ns, the port would be taken out of service. So a large asymmetry gets caught. One that stays below the limit doesn't, and no ECU reports a fault. In a vehicle, asymmetry comes from PHYs with different transmit and receive delays. The values are in the datasheet and belong in the configuration, per PHY type and speed.

### What it means for the vehicle

- **Fix the grandmaster.** Standard gPTP elects the best clock. With default-style settings, the lab camera should take over about 3 s after the gateway stops, and make its own time everybody's time. In a car you want the opposite: configured roles, and on loss each ECU runs on with its own clock (*holdover*), reports the lost synchronization, and marks the time invalid once the possible drift exceeds what the function tolerates. At 100 ppm, that's 0.1 ms after one second. A steady drift is easier for a fusion algorithm than a jump.
- **Plan the start.** AEB that fuses sensors can't be fully available before the time is. Put "time valid" into the start-up budget, next to link-up and service discovery.
- **Every switch on the path takes part.** One unaware switch in a carry-over zone ECU breaks the chain. Normally it simply doesn't forward the messages, so the neighbor never answers and the port stays out of service. If it does forward them, the delay jumps above the 800 ns limit. Both must end in a DTC, not in silence.
- **Where does the grandmaster sit?** In the central computer or the central switch. Think about what happens when that partition restarts during an update, and whether a second time domain is worth it.
- **Not everyone is on Ethernet.** The zone passes the time on over CAN (in AUTOSAR: `EthTSyn`, `StbM`, `CanTSyn`).

## QoS and TSN: important things first, and on time

**The problem.** A port sends one frame at a time. At 100 Mbit/s, a 1500-byte frame takes about 123 µs. If ten frames of an update arrive before the brake request, it waits more than a millisecond at that port. For a braking function, the worst case counts and not the average.

TSN (Time-Sensitive Networking) is a set of tools. You don't climb them like a ladder: 1 and 2 are the base, 3 to 5 solve different problems and can be combined.

| Tool | On the road | Mechanism | What it gives you |
|---|---|---|---|
| 1 | Blue lights on the roof | Priority in the VLAN tag (PCP) | The switch *recognizes* the brake request |
| 2 | Emergency lane | Several queues, strict priority | It overtakes in the queue |
| 3 | Ramp meter at the highway | Credit-based shaper (802.1Qav) | A class of streams gets its bandwidth, evenly spread, and no more |
| 4 | The truck pulls over mid-trip | Frame preemption (802.1Qbu, 802.3br) | A long frame blocks only until the next fragment |
| 5 | Road closed for a heavy transport, by timetable | Time-aware shaper (802.1Qbv) | A fixed time slot, calculable latency |

**Priority is only a mark.** On Linux, an application can set priority 5 and the frame still leaves with PCP 0, if nobody has configured the mapping. On an AUTOSAR ECU the same gap can sit between socket and VLAN configuration. From the component to the tag to the queue, every step has to be configured, and PCP ends at the router. Behind the gateway, the mapping has to be made again, for example from the DSCP field in the IP header.

**The shaper tames bursts.** A camera that sends a whole image at once blocks the port for everyone below it. The credit-based shaper (CBS) gives the queue an account, like a toll tag with a balance: you may pass the barrier while you aren't in debt. A large truck puts you deep into the red, and the balance recovers at a fixed rate. Nobody can pay in advance for a whole fleet.

Four rules describe the credit:

1. A frame may only start if the credit is **0 or above**.
2. While a frame of the queue is **sent**, the credit falls with the **sendSlope** = idleSlope - port rate.
3. While a frame **waits**, it rises with the **idleSlope**, the reserved bandwidth.
4. If the queue is **empty**, a negative credit recovers to 0, and a positive one is reset to 0.

{% include anim.html src="/assets/videos/automotive-ethernet/credit-based-shaper.mp4" alt="Animation: credit of a shaped queue over time. While a frame is sent, the credit falls steeply to minus 962 bytes; while the next one waits, it rises slowly to zero. A foreign frame delays the third frame and lets the credit rise to plus 123 bytes, so the fourth frame is on time again. With an empty queue, the credit stops at zero." caption="The sawtooth of a credit-based shaper on 100BASE-T1 with 8 Mbit/s reserved. Grey: a foreign frame of up to 123 µs. Values are calculated." %}

The two edges are so different because the link is much faster than the reservation. Here are the numbers for a frame of 1046 bytes and 8 Mbit/s, on the 10 Gbit/s virtual link of the lab exercise and on a 100BASE-T1 link in a car:

| Part of the sawtooth | Virtual link, 10 Gbit/s | 100BASE-T1 |
|---|---|---|
| Rising edge (idleSlope) | +1 byte/µs | +1 byte/µs |
| Falling edge (sendSlope) | -1249 bytes/µs | -11.5 bytes/µs |
| Time to send | 0.84 µs | 84 µs |
| Credit after sending | about -1045 bytes | about -962 bytes |
| Time to recover | about 1045 µs | about 962 µs |
| **Period** | **1.046 ms** | **1.046 ms** |

The period is the same, because the port rate cancels out: it's the frame size divided by the idleSlope, 8368 bits / 8 Mbit/s. So a burst of 20 camera frames takes about 20 ms and leaves evenly, whatever the link. On a real link, preamble, checksum and gap add 24 bytes to each frame, and the period becomes 1.07 ms. Plan reservations with that overhead.

**Above zero** the credit only rises if a frame has to wait although it's allowed to start, because a foreign frame occupies the wire. On 100BASE-T1, a frame of maximum size takes up to 123 µs, which is worth 123 bytes of credit. The upper limit, **hiCredit**, bounds this catching up, and **loCredit** bounds the debt. That's how a stream makes up for a delay without turning into a burst.

For the vehicle, this means: plan the bandwidth per stream, add the streams of a class plus a reserve, and keep the sum of all shaped classes below a share of the link (75 % is typical). A faulty camera then can't starve *other* classes. It can still starve the other cameras in its own class, because the shaper counts per class and not per stream. Against that, you need policing per stream at the first switch (802.1Qci). And what the shaper doesn't promise is a fixed latency.

**The time window guarantees, if the ECU cooperates.** The time-aware shaper opens and closes a gate per queue by a schedule. The lab exercise exaggerates it for the eye: 10 ms open in every 100 ms, and a sender that ignores the schedule and sends every 13 ms.

{% include anim.html src="/assets/videos/automotive-ethernet/time-aware-shaper.mp4" alt="Timeline animation: gates open for 10 ms every 100 ms. A sender that sends every 13 ms has its frames collected and sent in bursts of six or seven at each gate opening, waiting up to 86 ms. A sender aligned to the schedule sends 2 ms before each gate opening and waits 2 ms every time." caption="Same schedule, two senders. The gate makes latency predictable only if the sender knows the time." %}

The even stream turns into bursts. A schedule is only useful if the sending task, the switches and the receiving task share one clock and one plan. That reaches into the ECU: the task that computes the brake request has to finish just before its window, so the OS schedule and the network schedule become one timing design (the [scheduling post]({% post_url 2026-11-21-scheduling-heterogeneous-compute-part-1-gangs-pipelines-and-topology %}) looks at the ECU side). Before each window, a guard band keeps long frames out. Preemption makes that band small. The [detail post]({% post_url 2026-11-09-automotive-ethernet-in-detail-architecture-requirements-and-software-stack %}) has an animation of preemption across three hops.

Applied to our four functions:

| Function | Reasonable start | Add only if the analysis demands it |
|---|---|---|
| AEB | Highest control class, strict priority, small frames | Preemption or time window on slow links |
| Brake light | Control class like AEB (PCP 6 in Part 1), cyclic with E2E | Nothing, usually |
| Sound and reversing camera | Credit-based shaper | Time window for audio on a busy ring |
| Update and diagnostics | Low class, limited rate | Policing at the entry switch (802.1Qci) |

**What it means.** Time windows bring a schedule that has to be calculated for the whole vehicle, stored in every switch and recalculated when a flow changes. In a car that gets functions over the air, that's a real cost: **a fixed schedule and flexible software pull in opposite directions.** Reserve windows per class and leave room, instead of fitting them tightly around today's flows. IEEE 802.1DG-2025 [1] is the TSN profile for in-vehicle networks and a good starting point.

## Security: a network that believes everything

**The analogy.** A parking garage whose barrier opens for every known license plate. Anyone can print a plate.

**In detail.** Four mechanisms of this series believe whoever speaks. The lab tried the first two. The other two follow from how the protocols work:

| Mechanism | The lie | Effect in the car | Countermeasure |
|---|---|---|---|
| Switch learning | "I'm the brake" | Brake commands go elsewhere | Static FDB, learning off, VLANs per port |
| ARP | "The gateway is at :64" | Traffic runs through the attacker | Static ARP entries, MACsec |
| Service discovery | "I offer the brake service" | Functions use the wrong server | Allowed endpoints configured, filter on port 30490 |
| gPTP | "I'm the grandmaster" | Fusion works with a wrong time | Fixed roles, gPTP only on expected ports, MACsec |

The worst result of the ARP experiment was the quiet one. When the tester forwarded the traffic to the real gateway, the ping showed **0 % loss**. No DTC, no timeout, and the tester could have read every packet.

In a car, the stranger usually comes in through one of three places: the telematics unit and its apps, the OBD connector, or a cable that's reachable from outside, such as a camera in a mirror. Draw these three into your architecture and follow the lines inward.

**What it means for the vehicle.**

1. **Static configuration.** What isn't learned can't be forged.
2. **Segmentation** in switch and gateway. The mirror camera's port accepts its stream, its time messages and its diagnostics, and nothing else.
3. **Cryptography.** MACsec protects a link, but a compromised ECU on that link is still trusted. SecOC proves that a message comes from a holder of the key, end to end between ECUs, but doesn't hide it. TLS protects a diagnostic or backend session. They answer different questions ([vocabulary here]({% post_url 2026-11-01-security-vocabulary-part-2-keys-hardware-and-the-ecu %})).
4. **Detection.** A MAC address that moves between ports, or an unexpected offer, is worth a security event.

In consolidated compute, there's a fifth question: which partition sent this? Inside the central computer, the virtual switch and the hypervisor are part of the security concept, and of the safety concept.

## How the pieces map to the architectures

| | Domain | Distributed compute | Distributed zonal | Consolidated compute |
|---|---|---|---|---|
| VLAN plan | By domain | By domain and function class | By function class, across the ring | By criticality and partition |
| Routing | Central gateway | Vehicle computer | Every powerful zone | Central, some in hardware |
| Service discovery | Optional | Yes | Yes | Yes, static for critical paths |
| gPTP | ADAS and audio only | Backbone | Everywhere, with a plan for the broken ring | Everywhere, down to the zones |
| TSN | Rarely | Priorities, shapers | Plus redundancy (802.1CB) | Plus time windows or preemption |
| Diagnostics | Gateway to CAN | DoIP at the vehicle computer | DoIP, zones forward | DoIP, partitions with own addresses |
| Link security | At the gateway | Backbone | Every ring link | Every link, plus isolation inside |
| Biggest network risk | Gateway is the bottleneck | Star center fails | Ring analysis, spread logic | Every loop depends on the network |

Read it from left to right: the less a function owns its box, whether it moves into a zone or into the center, the more the network takes over from the ECU boundary. What used to be separated by housings is now separated by VLANs, gates, keys and partitions.

## Questions for your next architecture review

1. Which control loops cross the network, over how many hops, and what's the worst case with a full-size frame in front at each one? ([QoS and TSN](#qos-and-tsn-important-things-first-and-on-time))
2. Which functions must work before service discovery is done and before the time is valid? ([service discovery]({% post_url 2026-11-24-automotive-ethernet-for-the-sdv-part-2-addresses-services-and-diagnostics %}#service-discovery), [grandmaster](#what-it-means-for-the-vehicle))
3. Is the first message after wake-up allowed to be lost? If not, what prevents it? ([ARP]({% post_url 2026-11-24-automotive-ethernet-for-the-sdv-part-2-addresses-services-and-diagnostics %}#arp))
4. Who is the grandmaster, what happens when it restarts, and who detects a wrong time? ([asymmetry](#what-the-measurement-cant-see))
5. What do the headlamps and the brake light do when the center is silent? ([strengths and weaknesses]({% post_url 2026-11-24-automotive-ethernet-for-the-sdv-part-1-architectures-frames-and-switches %}#strengths-and-weaknesses))
6. Which flows are routed in software, and is there a way around the router? ([gateway]({% post_url 2026-11-24-automotive-ethernet-for-the-sdv-part-2-addresses-services-and-diagnostics %}#the-gateway-as-a-router))
7. Which tables are learned at runtime, and why? ([switch]({% post_url 2026-11-24-automotive-ethernet-for-the-sdv-part-1-architectures-frames-and-switches %}#the-switch))
8. What has to change in the network when the workshop replaces an ECU? ([switch]({% post_url 2026-11-24-automotive-ethernet-for-the-sdv-part-1-architectures-frames-and-switches %}#the-switch), [ARP]({% post_url 2026-11-24-automotive-ethernet-for-the-sdv-part-2-addresses-services-and-diagnostics %}#arp))
9. How does the schedule change when a function is added over the air? ([time windows](#qos-and-tsn-important-things-first-and-on-time))
10. Which test showed that each protection works? ([security](#security-a-network-that-believes-everything))

## Closing thought

It's tempting to see Ethernet as a faster CAN. These three parts show a different picture: ECUs that have to be found, services that have to be offered, clocks that have to agree, and queues that have to be planned. Each is simple on its own. Together they are what lets software move freely through the vehicle, and what decides whether a brake request still arrives on time when it does.

*Sources: [1] [IEEE 802.1DG-2025](https://1.ieee802.org/publication-ieee-802-1dg-2025/). Lab examples come from my own learning project. Animations: [manim](https://www.manim.community/), `scripts/manim/ethernet_scenes.py`.*
