---
layout: post
title: "Automotive Ethernet for the SDV, Part 1: Vehicle Architectures, Frames and Switches"
date: 2026-11-24
categories: [Communication]
tags: [communication, automotive-ethernet, software-defined-vehicle, zonal-architecture, central-compute, vlan, switch, 10base-t1s, architecture]
---

*This is Part 1 of a three-part post on how Ethernet works inside a software-defined vehicle (SDV). This part covers the vehicle architectures, the frames and the switches; [Part 2]({% post_url 2026-11-24-automotive-ethernet-for-the-sdv-part-2-addresses-services-and-diagnostics %}) covers addresses, services and diagnostics; [Part 3]({% post_url 2026-11-24-automotive-ethernet-for-the-sdv-part-3-time-tsn-and-security %}) covers time, TSN and security. Related: [Automotive Ethernet vs CAN FD]({% post_url 2026-11-08-automotive-ethernet-vs-can-fd-basics-pros-and-cons %}) and, for sizing and requirements, [Automotive Ethernet in Detail]({% post_url 2026-11-09-automotive-ethernet-in-detail-architecture-requirements-and-software-stack %}).*

> **TL;DR**
>
> - Software leaves the function-specific boxes and moves into zones, into the center, or both. The network moves into the control loops.
> - The stages are a trade, not a ladder: each one buys something and pays for it.
> - A zone *controller* runs functions, a zone *aggregator* only collects and forwards. Decide which one you are building.
> - Every Ethernet link in the car carries the same frame format, but "Ethernet" means at least three things: IP services, audio/video streams (AVTP), and time (gPTP).
> - Switches learn addresses and believe what they hear. In a vehicle, configure the tables statically.
> - The VLAN plan is an architecture decision: it separates brake from infotainment, and it carries the priority.

Draw any vehicle architecture of the last five years and you will find a few boxes, a few thick lines, and the word "Ethernet" next to them. The boxes get all the attention. This series is about the lines: what has to happen on them so that a function can move from one box to another at all.

Every topic follows the same pattern: an analogy from the automotive world, then what really happens, then what it means for your vehicle architecture.

## What's inside

- Four vehicle functions that we follow through the series
- Four SDV architectures, and what each one asks of the network
- Strengths and weaknesses of each, and when it fits
- Which link goes where in the car
- A map: the OSI layers in the vehicle
- The frame: one crate, many contents
- The switch: learning, flooding, and being fooled
- VLANs: separation and priority on one cable

## Four functions to follow

Abstract networks are easy to get right. So here are four functions of one car, chosen because they want opposite things:

| Function | Path in the car | What it needs from the network |
|---|---|---|
| **Automatic emergency braking (AEB)** | Camera and radar → fusion → brake | Bounded latency, common time, integrity |
| **Brake light** | Brake request → rear zone → lamp | Short latency, must work right after wake-up |
| **Surround sound and reversing camera** | Head unit → amplifiers, Ethernet camera → display | Steady bandwidth, synchronous playback |
| **Update and diagnostics** | Backend or workshop tester → every ECU | Throughput, access control, no hurry |

In the car of fifteen years ago, these four barely met. The brake light was a CAN signal, the camera had its own cable, and the tester plugged into CAN. In an SDV, they share switches and links.

The protocol examples come from a small lab: a virtual vehicle network with four ECUs (gateway, camera, brake, tester) and a software switch on a Linux server.

| ECU | MAC | Untagged network | VLAN 10 |
|---|---|---|---|
| Gateway | `02:00:00:00:00:01` | 10.0.0.1 | 10.0.10.1 |
| Camera | `02:00:00:00:00:02` | 10.0.0.2 | 10.0.10.2 |
| Brake | `02:00:00:00:00:03` | 10.0.0.3 | 10.0.10.3 |
| Tester | `02:00:00:00:00:64` | 10.0.0.100 | 10.0.10.100 |

There is no automotive PHY and no real switch chip in it, so its timing says nothing about a car. The switch, ARP and routing examples come from lab runs. From UDP and TCP onward, the numbers are calculated or expected from the configuration. They are not my measurements.

## Four SDV architectures

**The analogy.** Think of a car plant. The same cars leave it in all four cases. What changes is where decisions are made, and how much the plant depends on its forklifts.

- **Domain:** The body shop, the paint shop and final assembly each have their own warehouse and their own planners. If two shops have to coordinate, it goes through the main office.
- **Distributed compute:** Area warehouses appear. They store everything needed nearby, whichever shop it belongs to. A few planning offices make the decisions for the whole plant.
- **Distributed zonal:** The area warehouses get planners of their own, who can decide alone and talk to each other.
- **Consolidated compute:** One control tower plans everything. The areas only load and unload, fast and precisely.

The long ways between a shop's own warehouse and the line are the wiring harness. The forklifts and their routes are the network. And the more decisions are made far away from the line, the less happens when the forklifts stop. That's why the third plant copes better with a blocked road than the fourth.

**In detail.** The four steps follow the classification that suppliers currently use, for example NXP in its public deck [1]. Names differ between OEMs, and real vehicles mix the stages. The [detail post]({% post_url 2026-11-09-automotive-ethernet-in-detail-architecture-requirements-and-software-stack %}) uses three coarser styles: its *zonal* covers both distributed stages, its *central compute* is consolidated compute.

{% include anim.html src="/assets/videos/automotive-ethernet/sdv-architectures.mp4" alt="Animation: twelve software functions from body, powertrain, ADAS and infotainment move between four architectures. In the domain architecture each group sits in its own domain controller around a central gateway. In distributed compute, a vehicle computer, ADAS and infotainment computers and four zones form a star. In distributed zonal, high-performance zones in a ring host functions. In consolidated compute, all functions sit in one central box with six aggregators around it." caption="The functions stay the same. The box that hosts them changes, and with it the job of the network." %}

| Architecture | Who runs the software | What Ethernet does |
|---|---|---|
| **Domain** | Domain controllers, grouped by function | Connects domains to a central gateway, diagnostics, flashing |
| **Distributed compute** | Vehicle computer, ADAS and cockpit computers; zones hold the I/O | Star-shaped backbone |
| **Distributed zonal** | High-performance zones plus a central unit | Ring or mesh between zones |
| **Consolidated compute** | One central platform with isolated partitions | Links the center to aggregators and end nodes |

Follow the brake light through the four rows and the change becomes visible:

| Architecture | Path of the brake light | Ethernet hops in the path |
|---|---|---|
| Domain | Brake ECU → CAN → body controller → lamp | None, or one through the gateway |
| Distributed compute | Brake → vehicle computer → rear zone → lamp | One or two |
| Distributed zonal | Brake in the front zone → ring → rear zone → lamp | One to three, and more if the ring is broken |
| Consolidated compute | Front aggregator → center → rear aggregator → lamp | At least two, through the central switch |

The hop counts are typical, not universal. And Ethernet isn't mandatory here: for the single BCU of this blog, the brake light stays on [CAN FD]({% post_url 2026-11-08-automotive-ethernet-vs-can-fd-basics-pros-and-cons %}), which is ready right after wake-up without a link to train or a service to find. Once the request and the lamp sit in different zones, the path leads over the backbone, and Ethernet has to earn that: links that are up early, static addresses and endpoints, a high priority, and E2E protection. Many vehicles keep CAN FD as a second path for exactly this kind of signal.

Three consequences are easy to overlook.

**The network moves into the control loop.** In the domain car, a busy infotainment system could hardly delay the brake light, because it usually wasn't on the same wire. In consolidated compute, a queue in the central switch is part of the reaction time of a lamp. At 100 km/h, the car travels 2.8 cm in every millisecond that a frame spends waiting.

**The zone gets simpler or smarter, and that's a decision.** A zone controller runs functions such as window lifters or local lighting and can keep a safe default alive when the center is silent. A zone aggregator forwards, as fast and predictably as possible, and needs an answer to the question what the headlamps do without the center. The end of that road are end nodes with little or no software: a door handle sensor or an LED driver on 10BASE-T1S that the center controls directly. The OPEN Alliance works on a Remote Control Protocol (RCP) for this in TC18. Check its status before you plan with it.

**Mixed criticality meets on one cable.** AEB data, music, a workshop session and an update share a link. [Part 3]({% post_url 2026-11-24-automotive-ethernet-for-the-sdv-part-3-time-tsn-and-security %}) exists because of this.

### Strengths and weaknesses

The four stages are often drawn like a ladder, with consolidated compute at the top. They're a trade. Back in the plant: the control tower sees everything and can change the schedule of the whole site with one decision. But when the tower goes dark, every area stands still, unless someone taught the areas what to do alone.

Typical tendencies, not laws:

| Architecture | Strengths | Weaknesses | Fits when |
|---|---|---|---|
| **Domain** | Proven supply chain, one owner per domain. Control loops stay local. A failure tends to stay in its domain | Long wiring harness. Cross-domain functions squeeze through the gateway. Updates touch many ECUs | Much carry-over, few cross-domain functions |
| **Distributed compute** | Can be introduced step by step. Shorter harness, I/O close to the actuator. Functions can cross domains | Several large computers plus zones to maintain. Ownership is split. The center of the star is critical | You come from domains and put new functions on the vehicle computer |
| **Distributed zonal** | Shorter harness. A zone can fall back on its own. Redundant paths | Logic is spread. Timing across the ring is hard to prove. Powerful zones cost money, and their versions must match | Availability counts more than centralization |
| **Consolidated compute** | Functions, data and updates in one place. Simple zones, short harness | Center and network are part of every loop. Freedom from interference on one chip. Redundancy, cooling and quiescent current need answers. High upfront investment | A new platform, many updates over its life, a strong software team |

Two questions separate the four faster than any benchmark. **What must still work when the center is silent?** If the answer includes exterior lighting and braking, you need smart zones or a redundant center, and both have a price. **How often will the software change after start of production?** If rarely, much of the benefit of consolidation is never collected.

You also don't have to choose one for the whole car. Braking can stay in a domain with local loops, while body and comfort move to the center.

## Which link goes where

| Segment | Typical link | Why |
|---|---|---|
| Between central computers | Up to 10 Gbit/s | Sensor data, state shared between computers |
| Center to zone | 100 Mbit/s to 2.5 Gbit/s | Bundled I/O, radar, audio |
| Radar, lidar, telematics | 100 Mbit/s to 2.5 Gbit/s | Raw or preprocessed data decides |
| Zone to small end nodes | 10BASE-T1S, CAN FD, LIN | Cost per node decides |
| Camera and display | Often SerDes, sometimes Ethernet | Uncompressed video needs SerDes. Our reversing camera compresses and uses Ethernet |
| OBD connector | 100BASE-TX | What a workshop tester can plug into |

Two vehicle-specific points hide in this table. In the car, 100BASE-T1 and 1000BASE-T1 run on a single twisted pair, because every additional pair costs weight, money and space in the harness. And not every link may sleep. Whoever has to hear the key fob at night needs a path that can be woken, without keeping half the switches powered. That's why the topology and the sleep concept are one decision ([details here]({% post_url 2026-11-09-automotive-ethernet-in-detail-architecture-requirements-and-software-stack %})).

The frame looks the same on all the Ethernet links, so the protocols in this series don't depend on the speed. The timing does: the examples in Part 3 use 100BASE-T1. And 10BASE-T1S as a multidrop bus is different below the frame. Its nodes share one medium and take turns (PLCA), so what follows about switch ports, queues and gates doesn't apply inside such a segment.

## The map: OSI layers in the vehicle

The textbook model has seven layers. In the car, the interesting part is who skips some of them: streams and time sit directly on layer 2, ARP stands between two layers, and E2E and SecOC protect data from ECU to ECU, whatever is below. The short names in the picture are explained when their turn comes: the streams (AVTP) below, SOME/IP and DoIP in Part 2, gPTP and Time-Sensitive Networking (TSN) in Part 3.

<figure style="margin:1.5rem 0">
<img src="{{ '/assets/images/automotive-ethernet/osi-in-the-vehicle.svg' | relative_url }}" alt="OSI layers in a vehicle. Physical: 100BASE-T1, 1000BASE-T1, 10BASE-T1S. Data link: Ethernet frame, VLAN and switch, plus TSN and MACsec. AVTP and gPTP sit directly on layer 2. ARP links layers 2 and 3. Above IP: UDP and TCP, TLS, SOME/IP with service discovery, DoIP and UDS. E2E and SecOC run from ECU to ECU." style="width:100%;max-width:640px;height:auto;display:block;margin:0 auto;border-radius:6px;border:1px solid #e1e0dc">
<figcaption style="font-size:0.9rem;color:#52514e;margin-top:0.4rem">Simplified. The colors show which part of the series covers what; SOME/IP also runs over TCP, and DoIP uses UDP for discovery.</figcaption>
</figure>

## The frame: one crate, many contents

**The analogy.** Parts move through the plant yard in standard crates. The label shows the license plate of the truck the crate is for, the plate of the truck it comes from, and a code for the content: "wheels", "seats", "documents". The yard handles every crate by its plate. Only the receiver uses the content code, to send it to the right line.

**In detail.** An Ethernet frame starts with the destination MAC (6 bytes), the source MAC (6 bytes) and the **EtherType** (2 bytes), the content code. Then comes the payload, 46 to 1500 bytes, and a 4-byte checksum. The destination comes first so that a switch can start deciding after six bytes.

The lab has a small capture with typical vehicle traffic. Six of its frames, drawn to scale:

{% include anim.html src="/assets/videos/automotive-ethernet/frame-types.mp4" alt="Animation: six frames drawn to scale: an ARP request with padding, a SOME/IP request over IPv4 and UDP, a SOME/IP service discovery offer, an event with a VLAN tag, a gPTP Sync without IP, and an AVTP video frame with a VLAN tag and no IP. The EtherType field is highlighted in each." caption="Same start, different content. The EtherType decides which path a frame takes through the receiver." %}

| EtherType | Content | Vehicle function |
|---|---|---|
| `0x0806` | ARP | Finding the ECU behind an IP address ([Part 2]({% post_url 2026-11-24-automotive-ethernet-for-the-sdv-part-2-addresses-services-and-diagnostics %})) |
| `0x0800`, `0x86dd` | IPv4, IPv6 | SOME/IP services, diagnostics over DoIP |
| `0x8100` | VLAN tag | Separation and priority |
| `0x88f7` | gPTP | Common time for camera, radar, audio ([Part 3]({% post_url 2026-11-24-automotive-ethernet-for-the-sdv-part-3-time-tsn-and-security %})) |
| `0x22f0` | AVTP | Audio and video streams |

**Padding.** A frame has at least 64 bytes with the checksum, so 60 in a capture. A lamp command with one useful byte still costs a full minimum frame. And Ethernet doesn't know where the real data ends, so every protocol above needs its own length field, and every parser in an ECU has to check it.

**No IP at all.** gPTP and AVTP sit directly on Ethernet. A vehicle firewall that only understands IP addresses doesn't see your camera stream or your time.

**AVTP in two sentences.** The Audio Video Transport Protocol (IEEE 1722) carries samples and video data of a *stream*, from one talker to one or more listeners. Each packet can carry a *presentation time* in the common gPTP time, so that all amplifiers play the same sample at the same moment, whatever the path through the network was.

**What it means.** "Ethernet" in an architecture drawing is at least three things: services, streams and time. Give them separate rows in the communication matrix, because they have different owners, different tools and different failure modes. Also plan which CAN PDUs stay PDUs: a gateway can carry them over UDP unchanged, which is often the cheapest way to bring a carry-over ECU into a new architecture.

## The switch

**The analogy.** A new yard dispatcher knows no truck. The first crate for the truck with plate 03 is offered at every dock. But whenever a crate arrives *from* a truck, the dispatcher writes down its plate and the dock. After one shift, each crate goes straight to the right dock.

**In detail.** A switch does four things: **learn** the source MAC and its port, **forward** if the destination is known, **flood** to all other ports if it isn't or if it's a broadcast, and **forget** entries after a while, 300 s by default in Linux. The table is called FDB, forwarding database.

The dispatcher has a weakness: they believe every license plate. In the lab, one forged frame from the tester with the brake's source address was enough. The next brake command went to the tester.

{% include anim.html src="/assets/videos/automotive-ethernet/switch-learning.mp4" alt="Animation: the camera sends a frame to the brake, the switch floods it. After the brake has sent once, the switch knows its port and forwards only to the brake. Then the tester sends a frame with the brake's source address, the table entry moves to the tester's port, and the next brake command goes to the tester." caption="Learning is convenient and gullible. One forged frame redirects the traffic." %}

**What it means for the vehicle.**

- **There is nothing to learn.** No ECU changes its port while driving. Production switches get static tables, with learning off or limited per port. The variants of the vehicle (with or without radar, left- or right-hand drive) become variants of the switch configuration, with a part number and an update path.
- **Flooding is load.** Every flooded frame takes bandwidth on links that don't need it. The MAC filter of the receiving ECU normally drops foreign unicast frames in hardware. Broadcasts, and multicasts that the filter doesn't cover, reach the software, and on a small zone ECU that's CPU time taken from its functions.
- **Replacement is a use case.** If a workshop replaces the brake ECU, does the new one have a MAC that the switch accepts? Decide whether a MAC belongs to the part or to the position in the vehicle, before the first car is built.
- **Measure the protection.** In the lab, a `static` entry on the Linux bridge still moved to the attacker's port; only `static sticky` held. A protection you haven't tested is an assumption.

## VLANs

**The analogy.** A proving ground used by several vehicle programs at once. They share the same roads, but the sticker on the windshield decides which gates open. The color of the sticker also says who has the right of way: the emergency vehicle, the endurance test, the visitor.

**In detail.** A VLAN tag is 4 bytes between the source MAC and the EtherType: a marker (`0x8100`), 3 bits of priority (**PCP**), one bit "may be dropped first" (DEI), and 12 bits of VLAN ID. The event in the capture carries VLAN 10 and priority 5.

```
| destination | source | 8100 | PCP 3 | DEI 1 | VID 12 | EtherType | payload
```

A typical starting point for a vehicle, to be adapted:

| VLAN | Traffic | PCP | Rule |
|---|---|---|---|
| Chassis and ADAS control | AEB, steering, brake, brake light | 6 | No infotainment, telematics or OBD |
| Sensor data | Radar, camera objects | 5 | No infotainment |
| Audio and video | Surround sound, reversing camera | 4 | Only talkers and listeners of the streams |
| Body and comfort services | Interior light, doors, climate | 3 | No OBD |
| Diagnostics and update | DoIP, flashing | 2 | Entry only through the DoIP entity |
| Telematics and apps | Backend, smartphone | 0 | Reaches the others only through the firewall |

Two kinds of traffic don't fit into a row. gPTP is sent untagged, and the switch ports handle it themselves with a queue of its own. Service discovery and network management exist inside each VLAN that needs them.

**What it means.** A frame without a tag has no priority field, so critical application traffic is always tagged. And a tag alone protects nothing. The separation comes from the switch, which has to enforce which VLANs are allowed on which port. The bridge in the lab forwards every tag, so its VLAN 10 is a label and nothing more. Ask your switch supplier and your configuration tool the same question: what happens to a frame with VLAN 10 that arrives on the infotainment port?

How fine should the plan be? By domain is the natural choice in a domain architecture. In consolidated compute, several criticalities sit behind one physical port, so the VLANs have to follow partitions and criticality instead, down into the virtual switch of the central computer.

## Where this leaves us

The architecture decides which functions meet on a link. The frame format is the same everywhere, the switch moves it, and VLANs that are enforced keep the brake and the music apart. What's missing is how an ECU finds its partner in the first place, and how a function that moved to another box is found again. That's [Part 2]({% post_url 2026-11-24-automotive-ethernet-for-the-sdv-part-2-addresses-services-and-diagnostics %}).

*Sources: [1] R. Petre, D. Sridharan, "Networking for the software-defined vehicle: enabling the shift to consolidated compute", NXP, public presentation, November 2026 (architecture classification, link speeds; figures here are redrawn). On RCP and zonal aggregators: [Microchip](https://www.microchip.com/en-us/about/media-center/blog/2026/rcp-and-concurrent-paradigm-shift-to-zonal-architecture), [ST](https://www.st.com/en/applications/ee-architecture-software-defined-vehicle/sdv-enabled-endpoints.html). Animations: [manim](https://www.manim.community/), `scripts/manim/ethernet_scenes.py`.*
