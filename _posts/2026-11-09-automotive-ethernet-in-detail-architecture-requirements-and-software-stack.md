---
layout: post
title: "Automotive Ethernet in Detail: Architectures, Network Design, Requirements and the Software Stack"
date: 2026-11-09
categories: [Communication]
tags: [communication, automotive-ethernet, 100base-t1, 1000base-t1, 10base-t1s, zonal-architecture, tsn, vlan, some-ip, doip, macsec, autosar, threadx, netx-duo, requirements, architecture]
---

<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>mermaid.initialize({ startOnLoad: true, theme: "dark" });</script>

*This is the follow-up to [Automotive Ethernet vs CAN FD]({% post_url 2026-11-08-automotive-ethernet-vs-can-fd-basics-pros-and-cons %}), which covered the basics of both and where each belongs. This post goes deeper into Ethernet: how in-vehicle networks are structured, how you size one, which requirements the system, the hardware and the software have to meet, and what the software stack looks like, in AUTOSAR Classic and on ThreadX. The example is again the BCU from the [foundation series]({% post_url 2026-08-30-create-the-foundation-part-1-requirements-and-thinking %}) with its one Ethernet port.*

> **TL;DR**
>
> - Adding Ethernet to an ECU is a system decision, not a PHY on the board.
> - Design from flows: bandwidth per link, worst-case latency, VLANs, addresses, start-up, sleep and security zones.
> - Hardware and software requirements follow from that list, from PHY wake-up to bounded CPU load.
> - The AUTOSAR Classic stack and its ThreadX equivalent are mapped module by module, with the BCU as an example.

Adding Ethernet to an ECU looks like a hardware decision: put a PHY on the board, route a pair to the connector, done. In reality it's a system decision with consequences everywhere. The network needs a design (addresses, VLANs, priorities, latency budgets), the hardware needs the right MAC, PHY and maybe a switch, and the software grows by a whole protocol stack with its own startup sequence, security surface and test effort. This post walks through all of it, top down.

## What's inside

- Architectures: domain, zonal, central compute, and the topologies inside them
- Network design: flows, bandwidth and latency budgets, VLANs and priorities, addressing, start-up, sleep and wake-up, security zones
- System requirements
- Hardware requirements: MCU, PHY, switch, physical layer
- Software requirements
- The software stack: AUTOSAR Classic module by module, one message's way through it, and the ThreadX equivalent
- The BCU as a worked example
- A checklist

## Architectures

### From domains to zones

Ethernet arrived in most vehicles through the side door: as a fast diagnostic and flashing interface to a central gateway. From there, three architecture styles have developed, and many current vehicles sit somewhere between them:

- **Domain architecture.** ECUs are grouped by function (body, chassis, powertrain, infotainment, ADAS), each domain has its own buses, and a central gateway connects them. Ethernet links the gateway to the domain controllers and carries diagnostics. Our BCU, as a body domain controller with an Ethernet uplink, belongs here.
- **Zonal architecture.** ECUs are grouped by *location*. A few zone controllers (front, rear, left, right) collect the I/O of their area, distribute power and connect the local CAN, LIN and 10BASE-T1S buses. An Ethernet backbone connects the zones to one or a few central computers, where most of the function logic runs. This cuts the wiring harness, because sensors and actuators connect to the nearest zone instead of to their function's ECU at the other end of the car.
- **Central compute.** The logical end point: one or two high-performance computers run almost all functions in partitions or virtual machines, and the zones are mostly I/O and power. Ethernet is the only network fast enough in the middle.

<div class="mermaid">
flowchart TB
    subgraph Central
        HPC1["Central compute A"]
        HPC2["Central compute B"]
    end
    HPC1 <-- "multi-gig" --> HPC2
    HPC1 <-- "1000BASE-T1" --> ZFL["Zone front left"]
    HPC1 <-- "1000BASE-T1" --> ZFR["Zone front right"]
    HPC2 <-- "1000BASE-T1" --> ZRL["Zone rear left"]
    HPC2 <-- "1000BASE-T1" --> ZRR["Zone rear right"]
    ZFL <-- "1000BASE-T1" --> ZFR
    ZRL <-- "1000BASE-T1" --> ZRR
    ZFL --- E1["CAN FD, LIN, 10BASE-T1S<br/>sensors and actuators"]
    ZRR --- E2["CAN FD, LIN, 10BASE-T1S<br/>sensors and actuators"]
    HPC1 <-- "multi-gig" --> CAM["Cameras, radar"]
</div>

### Topologies inside the architecture

Because Ethernet links are point to point, the topology is built from switches. Four patterns come up:

| Topology | How | Pros | Cons |
|---|---|---|---|
| **Star** | One central switch, every ECU on its own port | Short paths (one or two hops), simple to analyze | Many cable runs to one place, the switch is a single point of failure |
| **Daisy chain** | A small switch in every ECU, each connected to the next | Short cables, few ports per ECU | Latency adds up per hop, one failed ECU cuts off everything behind it |
| **Ring** | A daisy chain closed into a loop | Survives one broken link | Needs configured paths or a ring protocol so that frames don't circulate. For seamless redundancy, IEEE 802.1CB sends duplicates on both ways and removes them at the end |
| **Multidrop** | 10BASE-T1S bus | One pair for several nodes, no switch ports | 10 Mbit/s shared, short range, still young in production |

Zonal designs typically combine them: a star or a small ring of zones around the central computers, and stars or multidrop buses inside each zone.

### Where the switch lives

- **Discrete switch** in the gateway, the zone controllers or the central computer, with 5 to 12 or more ports, TSN features, filtering and often MACsec.
- **Switch integrated into the MCU.** Some automotive microcontrollers have a small integrated switch with a few ports, which makes daisy chains and small zones cheap.
- **Endpoint only.** A single port with a PHY, no switch, like the BCU's uplink.

## Designing the network

A CAN network is designed from a communication matrix: which frame, which ID, which signals, which period. An Ethernet network starts from the same information, but has more knobs.

### 1. Start with flows, not cables

List every **flow**: source, destination (or multicast group), payload size, period or rate, maximum latency, priority, and its safety and security classification. A SOME/IP event from the BCU to the central computer, a DoIP session from the tester, a camera stream, a logging channel, the time synchronization messages. Everything else derives from that list: which link carries what, how loaded it is, which VLAN and priority the flow gets, and whether it needs TSN.

### 2. Bandwidth budget per link and direction

Ethernet links are full duplex, so each direction gets its own budget. For each link, add up the flows including all overhead, then check it against a target utilization. Leaving 40 to 50 percent headroom is common, both for growth and to keep queues short.

Overhead is easy to underestimate for small messages. A SOME/IP event with 16 bytes of data travels in a frame with an Ethernet header, an optional VLAN tag, IP and UDP headers and the SOME/IP header, plus preamble and inter-frame gap on the wire. Together that's an 82-byte frame, and about 100 bytes of wire time: 16 bytes of data cost more than six times their size. Bundling several small events into one frame (SOME/IP and the AUTOSAR socket adapter both support that) is the main lever.

{% include anim.html src="/assets/videos/communication/frame-overhead.mp4" alt="Animation: a 16-byte data block is wrapped by a SOME/IP header, UDP, IPv4, a VLAN tag, the Ethernet header and FCS, then preamble and inter-frame gap, until it occupies 102 bytes on the wire with a data share of 16 percent. Four such events take 408 bytes in four frames, but 198 bytes when bundled into one frame." caption="Every layer adds its header. Bundling several events into one frame shares the Ethernet, IP and UDP overhead and doubles the data share." %}

### 3. Latency budget per path

Each switch hop adds:

- **Serialization:** the time to put the frame on the wire. About 123 µs for a full 1500-byte frame at 100 Mbit/s, about 12 µs at 1 Gbit/s.
- **Switch processing:** a few microseconds in a store-and-forward switch.
- **Queueing:** the time the frame waits behind others on the output port. With strict priorities, a high-priority frame still waits for one lower-priority frame that's already being sent, because a frame can't be interrupted. In the worst case that's one more maximum-size frame per hop.

So a high-priority 100-byte frame across three hops of 100BASE-T1 can take about 0.4 ms in the worst case, even if the network is mostly idle, mostly because of large frames it has to wait for. If that matters, the options are: faster links in the backbone, a smaller maximum frame size for the bulk traffic, **frame preemption** (IEEE 802.1Qbu and 802.3br), or a **time-aware shaper** (802.1Qbv) that reserves time slots. For body functions, priorities plus a sensible frame-size limit are usually enough. For ADAS control paths, TSN is often needed.

{% include anim.html src="/assets/videos/communication/switch-latency.mp4" alt="Animation: a small blue control frame crosses three 100 Mbit/s links. With strict priority, it waits behind a grey 1500-byte bulk frame on every link and arrives after about 0.4 ms. With frame preemption, the bulk frame is split, the control frame goes almost at once and arrives after about 0.06 ms." caption="Same traffic, same throughput. With strict priority, the control frame waits for one full-size frame per hop. With frame preemption, it only waits for the next fragment boundary." %}

### 4. VLANs and priorities

VLANs separate traffic logically on the same cables. A typical plan has a handful of VLANs, by domain or by security level: for example, safety-relevant control, body services, diagnostics, infotainment, logging. A switch doesn't forward between VLANs. That takes a router, often a layer 3 function in the gateway or switch, and it only connects what its rules allow. This makes the VLAN plan part of the security architecture.

The VLAN tag also carries a 3-bit priority (PCP). A typical mapping puts time synchronization and the most time-critical control at the top, other control and services in the middle, diagnostics below that, and bulk data such as logging and updates at the bottom. Whatever the mapping, write it down once and generate the switch configuration and the ECU socket configuration from it.

### 5. Addressing

In-vehicle networks almost always use **static addressing**: each ECU's IP addresses (often IPv4, sometimes IPv6) are fixed in the network description. DHCP adds start-up time and failure modes nobody wants in a car. SOME/IP events and service discovery use **multicast**, so the multicast groups and which ports they reach are part of the design too. Each Ethernet port also needs a **MAC address**: unique, usually written into each unit in production. That's a production requirement that surprises teams new to Ethernet.

### 6. Start-up budget

Body functions are expected to react within a short time after wake-up. For an Ethernet path, the chain is:

1. MCU start and stack initialization
2. PHY initialization and **link training**, commonly specified in the tens of milliseconds
3. IP stack ready, sockets open
4. **Service discovery**: the server offers its service, the client finds it and subscribes, timed by configurable delays
5. First event or method call

Each step needs a budget, and the whole chain needs to be measured on real hardware. The usual levers are short initial delays in service discovery, static configuration everywhere, and sending an initial value right after a subscription instead of waiting for the next change.

### 7. Sleep and wake-up

When the vehicle is parked, most of the network sleeps. With Ethernet, that means deciding: which links can sleep, which ECUs must remain wakeable, how a wake-up travels through switches (OPEN Alliance TC10 defines sleep and wake-up over the data line), and how network management coordinates it (UDP network management in AUTOSAR). A switch that has to stay powered just to forward a wake-up costs quiescent current, so the topology and the sleep concept have to be designed together.

### 8. Security zones

The network design is where the security concept from a [TARA]({% post_url 2026-10-21-securing-the-foundation-part-1-threat-model-root-of-trust-and-boot %}) becomes concrete:

- **Segmentation:** VLANs plus filtering rules in the switches (which source may talk to which destination, on which port and protocol), so that a compromised infotainment unit can't reach the body controller directly.
- **Link protection:** MACsec on backbone links, with keys from the key management.
- **End-to-end protection:** SecOC for safety-relevant signals, independent of the path, plus E2E for safety.
- **Detection:** intrusion detection in the switches and gateways, reporting to a security event manager.

## System requirements

What the system specification of an Ethernet-connected ECU should cover, beyond "has a 100BASE-T1 port":

| Area | Requirements to define |
|---|---|
| **Performance** | Throughput per direction, maximum CPU load for networking, maximum number of sockets and services |
| **Timing** | End-to-end latency per flow class, jitter where relevant, time synchronization accuracy (if gPTP is used) |
| **Start-up** | Time from wake-up to link up, to service available, to first message received |
| **Power** | Quiescent current per sleep state, which wake-up sources (TC10, local, CAN), wake-up time |
| **Availability** | Behavior on link loss (fallback values, DTC, recovery time), redundancy if any |
| **Security** | Firewall rules, MACsec or not, SecOC per flow, DoIP authentication, robustness against malformed and flooding traffic, security event logging |
| **Diagnostics** | DoIP, link and cable diagnostics readable by DID, DTCs for link loss and quality degradation |
| **Debug and logging** | Port mirroring on switches for measurements, logging channels, timestamps (see [the debugging post]({% post_url 2026-11-08-debugging-is-a-feature-from-sil-to-the-field %})) |
| **Conformance and test** | Interoperability and conformance tests per the OPEN Alliance test specifications for the PHY and for the ECU's network stack |
| **Production** | MAC address programming, flashing over DoIP at the end of line, network configuration per variant |
| **EMC** | Emission and immunity limits for the PHY and the harness, according to the OEM's EMC specification |

## Hardware requirements

### Microcontroller

- **Ethernet MAC** with DMA and descriptor rings, and enough on-chip RAM for receive and transmit buffers. Bursty traffic needs buffers; a MAC with too little buffer memory drops frames under load.
- **Interface to the PHY or switch:** RMII for 100 Mbit/s, RGMII for 100 Mbit/s and gigabit, SGMII on faster parts. The choice affects pin count and layout.
- **Checksum offload** for IP, UDP and TCP, which saves noticeable CPU time at higher rates.
- **Hardware timestamping** (IEEE 1588 timestamp unit) if gPTP time synchronization is required. Software timestamps aren't accurate enough.
- **Crypto acceleration and an HSM** for SecOC, TLS for DoIP, and key handling for MACsec.
- **Hardware filtering** of MAC addresses and VLANs, so the CPU doesn't have to look at every frame.

### PHY

- The right standard for the link: 100BASE-T1 for most ECUs, 1000BASE-T1 for the backbone, 10BASE-T1S at the edge.
- **TC10 sleep and wake-up support**, low sleep current, and a wake-up output to the power supply.
- **Cable diagnostics:** detection of open and short circuits and a signal quality indicator, readable by software for DTCs and DIDs.
- Automotive qualification and the temperature range of the mounting location.

### Switch (if the ECU has one)

- Port count with growth, and the right mix of port speeds.
- **TSN features** as needed: priority queues, credit-based shaper, time-aware shaper, frame preemption, gPTP support.
- **Filtering and policing:** access control lists, rate limits per port and per stream, so that one misbehaving node can't flood the network.
- **MACsec** in the switch, if the links need it.
- Enough **buffer memory** for the worst-case bursts.
- A configuration path: the MCU configures the switch at start-up over SPI or MDIO, and that configuration has to be ready before traffic is expected.

### Physical layer

- **Common-mode choke and ESD protection** at each port, per the PHY vendor's reference design.
- **100 Ω differential routing** on the board, short and symmetrical.
- **Automotive connectors** specified for the data rate. Gigabit and multi-gigabit links need connectors and cables that are qualified for them; 100BASE-T1 runs on unshielded twisted pair up to about 15 m.
- The harness design in line with the PHY's channel specification (length, number of inline connectors).

## Software requirements

- **Throughput at bounded CPU load.** For example: 20 Mbit/s receive at no more than 10 percent of one core. Measured, not estimated.
- **Static memory.** Buffers, sockets and connections dimensioned at build time, no dynamic allocation in the network path of a safety-relevant ECU.
- **Robustness.** Malformed frames, wrong lengths, unknown services, broadcast storms and connection floods must not crash the stack or starve the CPU. Rate limiting in the driver or the switch, and fuzzing of the stack as part of the test.
- **Start-up time** as specified in the system requirements, with each step traceable in a trace.
- **Configuration from one source.** IP addresses, VLANs, sockets, SOME/IP services and switch configuration generated from the network description, never typed twice.
- **Diagnostics.** DTCs for link loss and degraded signal quality, DIDs for link state, error counters and cable diagnostics, DoIP for UDS.
- **Freedom from interference.** If safety-relevant software shares the CPU with the network stack, the stack must not be able to delay or corrupt it: separate tasks with time budgets, memory protection, and E2E for the safety-relevant data (as in the [foundation series]({% post_url 2026-10-19-create-the-foundation-part-4-swc-allocation-and-task-setup %})).
- **Security.** Only the ports and services the ECU actually needs are open. Every received byte is untrusted until it's checked.

## The software stack

### AUTOSAR Classic

In AUTOSAR Classic, Ethernet adds a stack of its own below the familiar COM layers. From the bottom up:

<div class="mermaid">
flowchart TB
    APP["SWCs via the RTE"]
    COM["Com / LdCom, SomeIpXf, SecOC"]
    PDUR["PduR"]
    SOAD["SoAd"]
    SD["Sd"]
    DOIP["DoIP"]
    NM["UdpNm"]
    TCPIP["TcpIp (IPv4/IPv6, UDP, TCP, ARP, ICMP)"]
    ETHIF["EthIf"]
    ETH["Eth (MAC driver)"]
    TRCV["EthTrcv (PHY driver)"]
    SWT["EthSwt (switch driver)"]
    APP --> COM --> PDUR --> SOAD
    SD --> SOAD
    DOIP --> SOAD
    NM --> SOAD
    SOAD --> TCPIP --> ETHIF
    ETHIF --> ETH
    ETHIF --> TRCV
    ETHIF --> SWT
</div>

| Module | Role |
|---|---|
| **Eth** | MAC driver: descriptors, DMA, buffers, interrupts |
| **EthTrcv** | PHY driver: link state, sleep and wake-up, cable diagnostics |
| **EthSwt** | Switch driver: port configuration, VLANs, mirroring, switch diagnostics |
| **EthIf** | Ethernet interface: abstracts controllers, transceivers and switches, handles VLANs per controller |
| **TcpIp** | The IP stack: IPv4/IPv6, ARP, ICMP, UDP, TCP |
| **SoAd** | Socket adapter: maps PDUs to sockets, bundles several PDUs into one frame, routes received data to PduR |
| **Sd** | SOME/IP service discovery: offering, finding and subscribing to services |
| **SomeIpXf** | SOME/IP transformer: serializes and deserializes data for SOME/IP |
| **LdCom** | Passes large or already serialized data between RTE and PduR, without signals |
| **DoIP** | Diagnostics over IP: vehicle announcement, routing activation, UDS messages to Dcm |
| **UdpNm** | Network management over UDP: coordinated sleep and wake-up |
| **EthSM** | State manager: brings the network up and down on behalf of ComM |
| **EthTSyn, StbM** | Time synchronization (gPTP) and the time base for the rest of the ECU |
| **SecOC, Csm, KeyM** | Message authentication and the crypto and key management behind it |
| **IdsM** | Intrusion detection: collects and reports security events |

**One message's way through it.** The BCU's LightCtrl component publishes the lamp state as a SOME/IP event:

1. `Rte_Write` hands the data to the RTE. The SOME/IP transformer serializes it and adds the second half of the SOME/IP header (request ID, versions, message type, return code).
2. LdCom passes the serialized data on as a PDU (signal-based data takes the way through Com). SecOC adds a MAC and freshness value if the flow requires it.
3. PduR routes the PDU to SoAd.
4. SoAd assigns it to the UDP socket of the event group, adds the first half of the header (message ID and length) and bundles it with other pending PDUs for the same destination.
5. TcpIp builds the UDP and IP headers, EthIf adds the VLAN tag and priority, Eth puts the frame into a transmit descriptor.
6. The MAC sends it, the PHY drives the pair, and the switch in the gateway forwards it according to its VLAN and priority.

On the receiving side the same path runs upward. If no client has subscribed to the event group yet, SoAd doesn't send it at all. That's where service discovery and start-up timing meet.

**PDUs over IP.** Not everything on Ethernet has to be SOME/IP. Signal-based PDUs, for example ones that also exist on CAN, can be sent over UDP as they are. A BCU acting as a gateway uses PduR to route CAN PDUs to Ethernet and back without touching the signals.

### On ThreadX

The AUTOSAR-on-ThreadX approach from [this series]({% post_url 2026-10-21-running-autosar-on-threadx-part-2-rte-communication-and-bsw %}) needs the same functions, from different building blocks:

| AUTOSAR module | ThreadX world |
|---|---|
| Eth, EthTrcv, EthSwt | The vendor's Ethernet and PHY driver, plus a switch driver if there is one, integrated as a NetX Duo network driver |
| TcpIp | **NetX Duo**, the TCP/IP stack of Eclipse ThreadX: IPv4/IPv6, UDP, TCP, BSD socket API, optional TLS |
| SoAd | A thin layer of your own that maps PDUs to sockets, or direct socket use in the communication layer |
| Sd, SomeIpXf | A SOME/IP library for microcontrollers, commercial or your own. Most open-source SOME/IP implementations target Linux |
| DoIP | A DoIP implementation on top of NetX Duo sockets, connected to your UDS stack |
| UdpNm, EthSM | Your network management and the link state handling in the driver |
| SecOC, Csm | The same SecOC logic as on CAN, backed by the HSM driver |

The structure stays the same. What changes is that you assemble and configure it yourself, which is exactly the trade-off the ThreadX series discusses. The two parts that take the most effort are SOME/IP with service discovery and the configuration tooling that keeps addresses, services and sockets consistent.

### On the central computer

On a high-performance computer with Linux or another POSIX system, the stack is the operating system's own networking, with SOME/IP or DDS on top, often behind AUTOSAR Adaptive's `ara::com`. The concepts are the same; the resources and the tooling are those of the IT world.

### Resources

As an order of magnitude, a microcontroller stack with TCP/IP, SOME/IP with service discovery, DoIP and a handful of services needs a few hundred kilobytes of flash and somewhere between tens and a couple of hundred kilobytes of RAM. Buffers dominate the RAM, and they scale with throughput and the number of sockets. The CPU load scales with the packet rate rather than the data rate: many small frames cost more than a few large ones. Measure both on the target early, with realistic traffic.

## The BCU as a worked example

Putting it together for our BCU with its one 100BASE-T1 port to the central gateway:

- **Architecture:** endpoint, no switch in the BCU. The gateway switch connects it to the central computer and to the diagnostic port.
- **Flows:** SOME/IP services offered by the BCU (light, wiper, door and window status, events at 10 to 100 ms and on change), methods called by the central computer (lock, unlock, light requests), DoIP for diagnostics and flashing, UDP network management, and a logging stream that's off by default.
- **Bandwidth:** the services need well under 1 Mbit/s. DoIP flashing is the only bulk flow, at the lowest priority.
- **VLANs:** two at the BCU's port. One for body services, one for diagnostics. The gateway filters which ECUs may reach which.
- **Latency:** two hops to the central computer, small frames, priority for control. Well within the tens of milliseconds body functions need, without TSN. The brake light request stays on CAN FD anyway.
- **Start-up:** link up and service availability budgeted and measured, short service discovery delays, initial values sent on subscription.
- **Security:** SecOC on the lock and unlock methods, authenticated DoIP, filtering in the gateway, security events into the IdsM.
- **Hardware:** the MCU's MAC with RGMII to a 100BASE-T1 PHY with TC10, checksum offload, HSM. No gPTP needed.
- **Software:** the AUTOSAR stack above, or NetX Duo plus SOME/IP and DoIP on ThreadX, with the network stack in its own tasks on the QM core, separated from the ASIL B core.

## Checklist

- [ ] Architecture and topology chosen, with the switch locations and the single points of failure known
- [ ] Flow list with size, rate, latency, priority, safety and security class for every flow
- [ ] Bandwidth budget per link and direction, with headroom
- [ ] Worst-case latency per critical path, including waiting behind maximum-size frames
- [ ] VLAN plan, priority mapping and filter rules, generated into switch and ECU configuration
- [ ] Static addresses, multicast groups and MAC address programming defined
- [ ] Start-up budget per step, measured on hardware
- [ ] Sleep and wake-up concept with TC10 and network management, quiescent current checked
- [ ] Security: segmentation, MACsec where needed, SecOC per flow, DoIP authentication, robustness tests
- [ ] Hardware: MAC with buffers and offload, PHY with TC10 and cable diagnostics, switch features, layout per reference design
- [ ] Software: throughput at bounded CPU load, static memory, configuration from one source, diagnostics, freedom from interference
- [ ] Conformance and interoperability tests planned from the start

Ethernet gives an ECU bandwidth, flexibility and a fast diagnostic path. In return, it asks for a network design, a bigger stack and much more configuration than CAN ever did. Planned from the start, that's a good trade. Discovered halfway through a project, it's a long list of surprises.
