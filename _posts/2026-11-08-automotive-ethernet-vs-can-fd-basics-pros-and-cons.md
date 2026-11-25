---
layout: post
title: "Automotive Ethernet vs CAN FD: The Basics, Then an Honest Pros and Cons"
date: 2026-11-08
categories: [Communication]
tags: [communication, can-fd, can-xl, automotive-ethernet, 100base-t1, 10base-t1s, some-ip, doip, tsn, secoc, macsec, zonal-architecture, architecture]
---

<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>mermaid.initialize({ startOnLoad: true, theme: "dark" });</script>

*The follow-up, [Automotive Ethernet in Detail]({% post_url 2026-11-09-automotive-ethernet-in-detail-architecture-requirements-and-software-stack %}), goes deeper into Ethernet architectures, network design, requirements and the software stack.*

*The example is the body control unit (BCU) from the [foundation series]({% post_url 2026-08-30-create-the-foundation-part-1-requirements-and-thinking %}), which we gave four CAN FD channels, eight LIN channels and one Ethernet port. This post explains why that mix makes sense.*

> **TL;DR**
>
> - Bit rate, baud rate, bandwidth and latency are different things. "Faster" needs a unit.
> - CAN FD: cheap, simple and deterministic for short control signals, and available early after wake-up.
> - Ethernet: bandwidth, diagnostics, flashing and services, at the price of a bigger stack and a network design.
> - Ethernet in the middle, CAN FD at the edges, and a well-designed gateway in between.

"Should we use Ethernet or CAN FD?" sounds like a technology question. It's mostly an architecture question, and the short answer is: both, in different places. To see why, it helps to know what each of them actually does on the wire, and what it costs you in software. So this post starts with the basics of both, then compares them criterion by criterion, and ends with a rule of thumb for where each one belongs.

## What's inside

- Four terms first: bit rate, baud rate, bandwidth, speed
- CAN FD basics: arbitration, frames, the two bit rates, what limits it
- Automotive Ethernet basics: the PHYs, switches, the protocol stack on top
- A side-by-side comparison with numbers
- Pros and cons per criterion: bandwidth, latency, wiring, cost, power and wake-up, start-up time, robustness, security, diagnostics, software effort, tooling
- The newcomers that blur the line: CAN XL and 10BASE-T1S
- Where each one belongs, using the BCU as the example

## First, four words that get mixed up: bit rate, baud rate, bandwidth and speed

Every comparison of buses sooner or later says one thing and means another. Four terms in particular:

- **Bit rate (data rate)** is what most people mean by all of these words: how many bits per second the bus transmits, in bit/s. "100 Mbit/s Ethernet" and "CAN FD with 2 Mbit/s" are bit rates. It's the *gross* rate: overhead such as headers, checksums, stuff bits and gaps between frames is included. What's left for your data is the **throughput** or, after all protocol layers, the **goodput**, and that's always noticeably lower.
- **Baud rate** counts **symbols** per second, in baud (Bd). A symbol is one state on the line. If a symbol has only two levels, it carries one bit, and baud rate equals bit rate. That's the case for CAN, which is why "CAN baud rate" is a harmless habit. Automotive Ethernet uses more levels to keep the frequencies on the cable low: 100BASE-T1 sends three-level symbols (PAM3) at 66.67 MBd, and each pair of symbols carries three bits, so 66.67 MBd carry 100 Mbit/s. 1000BASE-T1 uses PAM3 at 750 MBd. Baud rate matters for the hardware (cable, EMC, PHY design), bit rate for everyone else.
- **Bandwidth** has two meanings. In signal engineering it's a **frequency range** in hertz: how much spectrum a cable or channel can carry. In everyday networking it's a synonym for data rate ("we need more bandwidth"). This post uses it in the everyday sense, for the amount of data a link can carry.
- **Speed** is the vaguest of all. Usually it means bit rate again ("a faster bus"). It does *not* mean how fast the signal travels: on a twisted pair, any signal moves at roughly two thirds of the speed of light, about 5 ns per meter, whether it's CAN or gigabit Ethernet. What a faster bus shortens is the time to put a frame on the wire. And what an application actually feels is **latency**: the time from "send" in one ECU to "received" in another, including queues, switches and software.

So "Ethernet is faster than CAN FD" is true for bit rate and throughput. Whether it's faster in latency depends on the network, as the comparison below shows.

## CAN FD basics

CAN (Controller Area Network) has been in cars since the early nineties. CAN FD (Flexible Data rate, ISO 11898-1:2015) keeps everything that made CAN successful and fixes its biggest limit: eight bytes per frame at a maximum of 1 Mbit/s.

**The bus.** All nodes hang on one twisted pair, terminated with 120 Ω at both ends. The signal is differential: a *dominant* bit (logical 0) actively drives the two lines apart, a *recessive* bit (logical 1) lets them float back. If any node sends dominant, the bus is dominant. That simple property is the basis for everything else.

**Arbitration.** There is no master. Every node may start sending when the bus is idle. While sending its identifier, each node listens to the bus. A node that sends recessive but reads dominant has lost against a lower identifier and stops sending, without destroying the other frame. The frame with the lowest ID always wins, with no time lost. That's why CAN latency for high-priority messages is predictable: the ID *is* the priority, and worst-case response times can be calculated (the classic response time analysis for CAN is well established).

{% include anim.html src="/assets/videos/communication/can-arbitration.mp4" alt="Animation: three CAN nodes with IDs 0x123, 0x0F4 and 0x0F2 send their identifiers bit by bit. The bus row shows the resulting level. Node A sends a recessive 1 at ID8 while the bus is dominant and drops out; node B drops out at ID2; node C, with the lowest ID, wins and keeps sending." caption="Bitwise arbitration: every node reads back what it sends. A node that sends recessive and reads dominant stops and listens. The frame with the lowest ID is never disturbed, so no bus time is lost." %}

**Two bit rates.** The arbitration has to work across the whole bus within one bit time, because every node must see every other node's bit before the next one starts. That limits the arbitration rate to typically 500 kbit/s in vehicles. CAN FD's trick: once arbitration is over and only one sender is left, it switches to a faster bit rate for the data field (Bit Rate Switch), typically 2 Mbit/s in vehicles, up to 5 Mbit/s and in some cases 8 Mbit/s with good transceivers and a clean topology. Then it switches back for the acknowledge.

**Frames.** Up to 64 bytes of payload (in steps: 0 to 8, 12, 16, 20, 24, 32, 48, 64), a stronger CRC (17 or 21 bits plus a stuff bit counter) and the same 11-bit or 29-bit identifiers. A frame is a broadcast: every node receives it, and acceptance filters decide who cares.

**Error handling.** Every node checks every frame. A node that detects an error destroys the frame with an error flag, so everybody discards it, and the sender retransmits automatically. Error counters make a faulty node first passive and then disconnect it (*bus-off*), so one broken node can't block the bus forever.

**What it really carries.** A 64-byte frame at 500 kbit/s and 2 Mbit/s takes roughly 350 µs including stuff bits and the slow phases. That's about 1.4 Mbit/s of payload if the bus did nothing else. In practice you keep the bus load well below that (50 to 70 percent is a common design limit), so plan with well under 1 Mbit/s of useful payload per channel. That's plenty for control signals and far too little for cameras or software updates.

On top of the frames sits the usual automotive stack: signals packed into PDUs by COM, transport protocol for larger messages (ISO-TP, ISO 15765-2) for diagnostics, SecOC for authentication, E2E for safety, and network management with partial networking for selective wake-up.

## Automotive Ethernet basics

"Automotive Ethernet" isn't one thing. It's normal Ethernet framing and the normal IP stack on top of physical layers made for cars.

**The physical layers.** Gigabit office Ethernet uses four pairs. Automotive PHYs use **one twisted pair**. The point-to-point types run full duplex, with echo cancellation so both directions share the pair; 10BASE-T1S as a multidrop bus is half duplex. 100BASE-T1 runs unshielded, while gigabit and multi-gigabit links are often shielded:

| PHY | Standard | Rate | Topology | Typical use |
|---|---|---|---|---|
| 10BASE-T1S | IEEE 802.3cg | 10 Mbit/s, shared | Multidrop bus, PLCA for collision-free access | Edge: sensors, actuators, a CAN replacement candidate |
| 100BASE-T1 | IEEE 802.3bw (from BroadR-Reach) | 100 Mbit/s | Point to point, up to 15 m | Most ECU links today |
| 1000BASE-T1 | IEEE 802.3bp | 1 Gbit/s | Point to point | Backbone, ADAS, central compute |
| 2.5/5/10GBASE-T1 | IEEE 802.3ch | multi-gigabit | Point to point | Cameras, high-end compute links |

**Switches instead of a bus.** Apart from 10BASE-T1S, every link connects exactly two devices. A network is built from switches, often integrated into a gateway, a zone controller or the central computer. Each frame travels hop by hop: received, checked, queued, forwarded. That's the fundamental difference from CAN: there's no shared medium and no arbitration, but there are **queues**, and queues mean variable latency.

**Frames.** Up to 1500 bytes of payload per frame, with about 38 bytes of overhead on the wire (preamble, header, checksum, inter-frame gap) plus 4 for a VLAN tag. VLAN tags also carry a priority (802.1Q), which switches use to pick the queue.

**The stack on top.** This is where Ethernet stops being "a faster CAN":

- **IP, UDP, TCP:** the normal internet protocols, usually IPv4 or IPv6 with static configuration.
- **SOME/IP:** service-oriented communication. A server offers a service with methods, events and fields, clients find it through service discovery (SOME/IP-SD) and subscribe. Instead of "this signal is in frame 0x1A3 every 10 ms", it's "who offers the light service?".
- **DoIP (ISO 13400):** UDS diagnostics over IP. The main reason many ECUs got their first Ethernet port: flashing and diagnostics at 100 Mbit/s instead of a few hundred kbit/s.
- **AVB/TSN:** time synchronization (gPTP, IEEE 802.1AS) and traffic shaping (credit-based shaper 802.1Qav, time-aware shaper 802.1Qbv) when you need bounded latency over switches.
- **Security:** MACsec (IEEE 802.1AE) per link, IPsec or TLS end to end, or SecOC as on CAN.
- **Power management:** sleep and wake-up over the data line are defined by the OPEN Alliance (TC10), since Ethernet had no wake concept of its own.

## Side by side

| | CAN FD | 100BASE-T1 | 1000BASE-T1 |
|---|---|---|---|
| Gross rate | 0.5 Mbit/s arbitration, 2 to 5 Mbit/s data | 100 Mbit/s per direction | 1 Gbit/s per direction |
| Max payload per frame | 64 bytes | 1500 bytes | 1500 bytes |
| Useful payload, realistic | well under 1 Mbit/s per channel | tens of Mbit/s per link | hundreds of Mbit/s per link |
| Topology | Bus, all nodes share it | Point to point plus switches | Point to point plus switches |
| Access | Priority arbitration by ID | Full duplex, queues in switches | Full duplex, queues in switches |
| Latency | Bounded, calculable per ID | Low, but depends on hops and queue load. Bounded with TSN | As 100BASE-T1, lower per hop |
| Communication model | Signals in broadcast frames | Signals, PDUs or services (SOME/IP) | Same |
| Wake-up | Wake-up pattern, selective wake with partial networking | TC10 sleep and wake | TC10 |
| Typical start-up | Ready almost immediately | Link training plus IP and service discovery | Same |
| Software stack | Small: CAN driver, COM, TP | Large: Ethernet driver, switch driver, TCP/IP, SOME/IP, SD, DoIP | Same |

## Pros and cons, criterion by criterion

### Bandwidth

**Ethernet wins, and not by a little.** One 100BASE-T1 link carries more than all four CAN FD channels of the BCU together, in each direction at the same time. For cameras, radar data, logging, over-the-air updates or a backbone between computers, CAN FD isn't an option at all.

**But bandwidth isn't the point for most body functions.** A window lifter command is a few bits every 20 ms. The BCU's light, wiper and door signals fit comfortably on CAN FD. Paying for Ethernet bandwidth you don't need is a cost, not a feature.

### Latency and determinism

**CAN FD's strength.** The lowest ID always gets the bus next, the worst case is calculable, and there are no queues hidden in switches. For a brake light request that has to arrive within a few milliseconds, that's a simple argument in a safety case. The calculation has its own assumptions, though: a bounded number of errors and retransmissions, and transmit buffers that really send the lowest ID first.

**Ethernet is fast but needs care.** A frame with 1500 bytes of payload takes about 123 µs on a 100 Mbit/s link, and a switch typically has to receive a frame completely before it forwards it. Each hop adds that, plus waiting behind whatever is already queued. Priorities help, TSN shapers give real guarantees, but both need configuration, verification and switch hardware that supports them. "Ethernet is faster" is true for throughput, but not automatically for worst-case latency.

### Topology and wiring

**CAN FD:** one pair for many nodes, easy to extend by adding a node to the bus. But the higher the data rate, the more stubs, star points and long lines hurt the signal. At 5 Mbit/s and above, the topology needs serious attention, and that's the practical ceiling of CAN FD.

**Ethernet:** point to point means one cable per device and a switch port at the other end. More cable runs and more switch ports, but each link is electrically simple and fully isolated from the others. An electrical fault stays on its link. A node that floods the network is still a problem, as a babbling node is on a bus, but the switch can contain it with rate limits and policing (CAN's error handling limits a babbling node too, but doesn't eliminate it). Zonal architectures turn the point-to-point property into an advantage: a few fast links from the zone controllers to the central computer, short local buses from there.

### Cost

**CAN FD is cheap per node:** a transceiver and a controller that's integrated into almost every automotive MCU. No switch, no magnetics.

**Ethernet costs more per node:** a PHY per port, common-mode chokes, and switch silicon somewhere. The MCU needs a MAC and enough RAM and flash for the stack. Per bit transported, Ethernet is far cheaper. Per node with low bandwidth needs, it's more expensive, which is exactly why 10BASE-T1S exists.

### Power and wake-up

**CAN FD:** transceivers with very low standby current, wake-up on bus activity, and partial networking so that only the ECUs addressed by a wake-up frame start. Mature and well understood.

**Ethernet:** PHYs draw more power, and wake-up and sleep only became standardized through TC10. A switch that has to stay awake to forward wake-up requests costs quiescent current. For ECUs that must be reachable while the vehicle is parked, this adds up and needs careful design.

### Start-up time

Often overlooked, and important for a BCU. When you open the door, the interior light is expected immediately.

- **CAN FD** is ready as soon as the transceiver and controller are, typically within a few milliseconds after the MCU starts.
- **Ethernet** first needs link training, then the IP stack, and with SOME/IP, the service discovery: the client has to find the service before it can subscribe. Link-up alone is commonly specified in the tens of milliseconds, and the whole chain needs explicit budgeting (static IP addresses, short discovery timers, initial events) to stay well under the reaction times body functions need.

### Robustness and EMC

Both are differential and run on twisted pairs in production cars, and both are proven at scale. CAN FD has decades of experience with fault tolerance (for example, how the bus behaves when one line is shorted). Automotive Ethernet PHYs have stricter EMC requirements and depend on correct cabling and connectors, especially at gigabit rates. Neither is fragile, but Ethernet leaves less margin for sloppy harness design.

### Security

**CAN FD:** no built-in security. SecOC adds authentication with a truncated MAC and a freshness value, which costs payload bytes. That hurt in classic CAN with 8 bytes and is much more comfortable with 64. There's no confidentiality, and the bus itself doesn't know who sent a frame: anyone on it can send any ID. How truncated MACs trade length against forgery chances is explained in the [security vocabulary]({% post_url 2026-10-30-security-vocabulary-part-1-the-crypto-toolbox %}).

**Ethernet:** more options and more attack surface. MACsec protects each link with hardware support, IPsec and TLS work end to end, and the switch can act as a firewall (VLANs, filtering by port). But an IP stack is a big parser that receives data from outside, and DoIP, TCP and SOME/IP-SD all need hardening. Ethernet doesn't make security easier. It makes it more powerful and more work (see [Securing the Foundation, Part 2]({% post_url 2026-10-21-securing-the-foundation-part-2-updates-bus-and-diagnostics %})).

### Diagnostics and flashing

**This is Ethernet's strongest argument for most ECUs.** Over CAN FD, ISO-TP moves well under 1 Mbit/s of useful data, and a few megabytes of software take minutes. Over DoIP at 100 Mbit/s, the bus stops being the bottleneck and the flash write speed becomes the limit. For end-of-line flashing in the plant, workshop updates and over-the-air updates distributed inside the car, that's a big difference in time and cost.

### Software effort and resources

**CAN FD:** a small, mature stack. Driver, interface, COM, transport protocol, network management. A few tens of KB, well understood by every team and every tool.

**Ethernet:** an Ethernet driver, often a switch driver, a TCP/IP stack, SOME/IP with service discovery, DoIP, possibly TSN and MACsec. More RAM, more flash, more CPU load (checksums, packet handling, crypto if not offloaded), more configuration and more to test. On a Cortex-M7 like the BCU's it's manageable. On a small body MCU it might not be.

**The communication model changes too.** Service-oriented communication with SOME/IP is a different way of thinking from the signal-based CAN world: services, subscriptions, discovery, versioning. That's a real advantage for flexible software architectures and updates, and a real learning curve for teams.

### Tooling and skills

Every automotive team can read a CAN trace. The tools for logging, simulation, restbus and analysis are mature and familiar. Ethernet tooling is good and getting better, but capturing on point-to-point links needs taps or port mirroring, decoding SOME/IP needs the service descriptions, and debugging a timing problem across three switches is a different job than looking at one CAN trace.

### Summary

| Criterion | CAN FD | Automotive Ethernet |
|---|---|---|
| Bandwidth | − enough for control, not for data | **+ orders of magnitude more** |
| Worst-case latency | **+ calculable by design** | ○ good, guaranteed only with TSN and effort |
| Wiring and topology | + one bus for many nodes | ○ more links, but isolated and zonal-friendly |
| Cost per low-bandwidth node | **+ very low** | − PHY, switch port, more MCU resources |
| Power and wake-up | **+ mature, partial networking** | − higher, TC10 needed |
| Start-up time | **+ almost immediate** | − link-up plus discovery, needs budgeting |
| Security | ○ SecOC only, no confidentiality | ○ more options, more attack surface |
| Diagnostics and flashing | − slow for large images | **+ DoIP, fast** |
| Software effort | **+ small, mature stack** | − large stack, new communication model |
| Flexibility and scalability | − frame layouts fixed at design time | **+ services, VLANs, higher rates on the same concepts** |
| Tooling and team experience | **+ everyone knows it** | ○ good tools, less experience |

## The newcomers that blur the line

Two technologies are closing the gap from either side:

- **CAN XL** (ISO 11898-1:2024): up to 2048 bytes of payload and data rates up to about 20 Mbit/s, with CAN's arbitration. It can carry Ethernet frames, which makes it a candidate for the edge of an IP-based architecture without leaving the CAN world.
- **10BASE-T1S** (IEEE 802.3cg): Ethernet on a multidrop bus, with PLCA giving each node a turn so there are no collisions. 10 Mbit/s shared, no switch port per node, and IP all the way to the sensor. It targets exactly the cost advantage of CAN.

Both are young in production. Watch them, especially for new zonal designs, but don't expect them to change the overall picture: fast point-to-point links in the middle, cheap shared buses at the edge.

## Where each one belongs

The trend in vehicle architecture is from many domain ECUs to a few central computers and zone controllers. That trend answers most of the question:

<div class="mermaid">
flowchart LR
    CC["Central compute"] <-- "1000BASE-T1" --> ZF["Zone front"]
    CC <-- "1000BASE-T1" --> ZR["Zone rear"]
    CC <-- "100BASE-T1" --> BCU["BCU"]
    BCU <-- "CAN FD" --> DOOR["Door ECUs"]
    BCU <-- "CAN FD" --> CLIM["Climate"]
    BCU <-- "LIN" --> SW["Switches, small actuators"]
    ZF <-- "CAN FD, LIN, 10BASE-T1S" --> EDGE["Sensors, actuators"]
</div>

For the BCU, that means:

- **One Ethernet port** to the central computer or the gateway: diagnostics and flashing over DoIP, services offered to the rest of the vehicle (light, wiper, door status), and a path for over-the-air updates.
- **Four CAN FD channels** to the ECUs it controls directly or that send it time-critical requests, like the brake light request from the [foundation series]({% post_url 2026-10-19-create-the-foundation-part-4-swc-allocation-and-task-setup %}): low latency, calculable, fast start-up, small software.
- **Eight LIN channels** to switches and small actuators, where even CAN FD would be overkill.

Is a BCU still a single ECU at all? In many vehicles on the road and in development today, yes: a body domain controller with its own box, its own I/O and its own CAN and LIN channels, like ours. In zonal architectures, the BCU as a box goes away. Its functions split along two lines: the logic (light, wiper and door strategies, the mode manager) moves into a central computer or a body domain partition on it, and the I/O (lamp drivers, lock motors, switch inputs) moves into the zone controllers, sorted by where in the car it sits rather than by function. In practice there are hybrids too. A front zone controller often is the former BCU plus the front power distribution, and keeps much of the body logic. For this blog's example, the BCU stays a single ECU with an Ethernet uplink, which is a realistic step on the way to zonal.

A rule of thumb that has held up for me:

- **Use CAN FD** for control loops and short, time-critical signals between a handful of ECUs, for anything that must work within milliseconds after wake-up, and for small MCUs where an IP stack would dominate the resources.
- **Use Ethernet** for the backbone, for anything with real data volume (cameras, logging, updates), for diagnostics and flashing, and where service-oriented software and later extension matter more than the cost of the node.
- **Use both** in almost every ECU that sits between the central computer and the edge, which in a modern vehicle is most of them.

The question isn't "Ethernet or CAN FD". It's where in your architecture you need bandwidth and flexibility, and where you need cheap, simple determinism. The answer is usually: Ethernet in the middle, CAN FD at the edges, and a gateway in between that someone has to design properly. How to design the Ethernet part is the topic of [the follow-up post]({% post_url 2026-11-09-automotive-ethernet-in-detail-architecture-requirements-and-software-stack %}).
