---
layout: post
title: "Automotive Ethernet for the SDV, Part 2: Addresses, Services and Diagnostics"
date: 2026-11-24
categories: [Communication]
tags: [communication, automotive-ethernet, software-defined-vehicle, arp, ipv4, some-ip, service-discovery, doip, uds, autosar, architecture]
---

<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>mermaid.initialize({ startOnLoad: true, theme: "dark" });</script>

*This is Part 2 of a three-part post on how Ethernet works inside a software-defined vehicle. [Part 1]({% post_url 2026-11-24-automotive-ethernet-for-the-sdv-part-1-architectures-frames-and-switches %}) covered the vehicle architectures, frames and switches; this part covers addresses, services and diagnostics; [Part 3]({% post_url 2026-11-24-automotive-ethernet-for-the-sdv-part-3-time-tsn-and-security %}) covers time, TSN and security.*

> **TL;DR**
>
> - MAC addresses name the next hop, IP addresses the final ECU. ARP connects the two, and nobody checks its answers.
> - The first message after wake-up can be lost while ARP is running. If the first brake light frame matters, use static entries.
> - The gateway between VLANs is the place for the vehicle firewall, and a bottleneck if it routes in software.
> - SOME/IP turns CAN signals into services. The interface version becomes part of the vehicle architecture.
> - Service discovery finds functions that moved to another ECU. Its TTL is far too slow as fault detection for a control loop.
> - DoIP hides the architecture from the workshop: an ECU needs neither IP nor Ethernet to be diagnosed.

In [Part 1]({% post_url 2026-11-24-automotive-ethernet-for-the-sdv-part-1-architectures-frames-and-switches %}), we put four vehicle functions on one network: emergency braking, the brake light, surround sound with a reversing camera, and updates with diagnostics. This part answers how they find each other. The question sounds trivial, until a function moves from an ECU to the central computer by software update and everyone who used it has to notice.

This part climbs from layer 2 to layer 7; the [OSI map in Part 1]({% post_url 2026-11-24-automotive-ethernet-for-the-sdv-part-1-architectures-frames-and-switches %}#the-map-osi-layers-in-the-vehicle) shows where each piece sits.

## What's inside

- Two addresses for one ECU, and ARP in between
- The gateway as a router and firewall
- UDP, TCP and multicast: which vehicle data goes where
- SOME/IP: from signals to services
- Service discovery: start-up, variants and failures
- DoIP and UDS: the workshop entrance

The lab network is the one from Part 1: gateway 10.0.0.1, camera 10.0.0.2, brake 10.0.0.3, tester 10.0.0.100, with MAC addresses ending in :01, :02, :03 and :64. ARP and routing examples come from lab runs. The numbers after that are calculated or expected from the configuration, not measured.

## Two addresses for one ECU

**The analogy.** A new car leaves the plant for a dealer in another country. Its papers always say "dealer 4711": that's the IP address, and it contains the place. But on the yard, the car is handed to the truck with a certain license plate, then to a ship, then to another truck. The plate is the MAC address. It says who takes the car *next*, and nothing about where that truck comes from. The papers stay, the plates change with every leg.

**In detail.**

| | MAC address | IP address |
|---|---|---|
| Answers | Which ECU gets the frame **next**? | Which ECU gets the packet **in the end**? |
| Valid | Up to the next router | Across the vehicle |
| Structure | Flat, says nothing about the place | Network plus host |
| Changes on the way | At every router | Never (without NAT) |
| Comes from | Programmed at the end of the line | Network description, static |

When the camera sends to an IP address, its stack decides in this order: which interface and next hop (routing table), which MAC that next hop has (neighbor cache), and then it builds the frame.

### ARP

**The analogy.** On the yard, a foreman has a car for 10.0.0.1 and doesn't know which truck serves that address. So they use the loudspeaker: "Who takes cars for 10.0.0.1? Please tell the truck with plate 02." Everyone hears it. One driver answers, directly to plate 02: "That's me, my plate is 01." The foreman writes it down, because nobody wants to use the loudspeaker all day.

**In detail.** In the lab, `ping 10.0.0.1` from the camera with an empty cache produces exactly two ARP frames before the first ping leaves:

```
02:00:00:00:00:02 > ff:ff:ff:ff:ff:ff, ARP, length 42: Request who-has 10.0.0.1 tell 10.0.0.2
02:00:00:00:00:01 > 02:00:00:00:00:02, ARP, length 42: Reply 10.0.0.1 is-at 02:00:00:00:00:01
```

{% include anim.html src="/assets/videos/automotive-ethernet/arp-resolution.mp4" alt="Animation: the camera holds an IP packet because the MAC address of 10.0.0.1 is unknown. It broadcasts an ARP request to gateway, brake and tester. The gateway learns the camera's address from the request and answers with a unicast reply. The camera's cache changes from incomplete to reachable, and the waiting packet is sent." caption="The question reaches everyone, the answer only the camera. The gateway learns from the question, the brake does not." %}

The camera learned the gateway from the answer. The gateway learned the camera **from the question**, because it was meant and needs the address for its reply. The brake saw the question too, and stored nothing. Entries get stale after 15 to 45 s (Linux defaults) and are then checked with a targeted question.

**What it means for the vehicle.**

- **The first message after wake-up may be lost.** Linux holds the packet until ARP is done. In AUTOSAR, `TcpIp_UdpTransmit` can return `TCPIP_E_PHYS_ADDR_MISS`, and the message is gone unless someone repeats it. For a cyclic brake light signal every 10 ms this costs one cycle. For a one-time "unlock the doors" event, it costs the unlock.
- **Wake-up is a broadcast storm in miniature.** When the car wakes, dozens of ECUs ask for each other at the same moment, in the start-up window with the tightest timing. Static entries remove that load and the risk of forged answers in one step.
- **Replacing an ECU needs a plan.** When the lab replaced a device by one with the same IP and a new MAC, between 10 and 50 pings were lost, one per second. With a short announcement at start (*gratuitous ARP*), the replacement was reachable at once. With static entries, the MAC must follow the position in the vehicle, or the workshop has to reconfigure the partners.
- **IPv6** uses NDP instead. The idea stays, the details don't: the question goes to a multicast group instead of everyone, and by default an ECU first checks that nobody else uses its address (duplicate address detection), which costs start-up time unless it's configured away.

## The gateway as a router

**The analogy.** A car crosses from ship to truck in a port. The car and its order don't change. But the shipping papers are replaced by road papers, customs adds a stamp, and customs may say no.

**In detail.** In the lab, the camera loses its VLAN 10 interface and reaches the brake through the gateway:

```
:02 > :01,                 ttl 64, 10.0.0.2 > 10.0.10.3
:01 > :03, 802.1Q vlan 10, ttl 63, 10.0.0.2 > 10.0.10.3
```

{% include anim.html src="/assets/videos/automotive-ethernet/router-hop.mp4" alt="Animation: a packet from the camera to the brake travels with MAC 02 to 01, IP 10.0.0.2 to 10.0.10.3 and TTL 64. At the gateway the Ethernet header is removed, and a new one with MAC 01 to 03, VLAN tag 10 and TTL 63 is added. The IP addresses stay the same." caption="A switch changes nothing. A router builds a new envelope for every hop." %}

The router checks the header, lowers the TTL, adjusts the checksum, picks the next hop and builds a new Ethernet header. On Linux, a host and a router differ by one setting, `ip_forward`. With it off, the lab gateway discarded the packets without any message.

The answer took a different path. The brake also has an address in 10.0.0.0/24, so it replied directly, past the gateway. **There and back are two independent decisions.** A vehicle firewall that only sees one direction is easy to build by accident.

**What it means for the vehicle.**

| Flow | Switched or routed? | Reason |
|---|---|---|
| Radar objects → AEB fusion | Switched, same VLAN | Latency, filtered in the switch hardware |
| AEB → brake | Switched, same VLAN | Latency |
| Infotainment → vehicle speed | Routed, read only | Firewall: the cockpit may know, not command |
| App → "open trunk" | Routed, then checked by a service | Authorization is an application decision |
| Tester → any ECU | DoIP entity, not IP routing | Access control per tester |

Control loops should not be routed in software: the gateway's CPU load would become part of the braking distance. And give an ECU an address only in the networks it needs, or it'll find the back door by itself, as the brake did. In consolidated compute, part of this routing moves into the virtual switch of the central computer. It needs the same rules and the same review.

## UDP, TCP and multicast

**The analogy.** UDP is a turn signal: it blinks, and nobody confirms. If someone misses one blink, the next follows. TCP is the handover of a new car: ID, checklist, signature on every page. Multicast is the traffic announcement on the radio: sent once, heard by those who tuned in.

**In detail.** The IP address finds the ECU, the **port** finds the software component behind it. UDP adds ports and a checksum in 8 bytes. TCP adds order, repetition and flow control. Sending 6 bytes typically takes **eight** segments over TCP, including setup and teardown, and one over UDP.

**Multicast** needs no ARP. There's no single receiver to ask, so the MAC follows from the group address by a fixed rule: `01:00:5e` plus the lower 23 bits. `224.244.224.245` becomes `01:00:5e:74:e0:f5`. At wake-up, a service offer doesn't have to wait for ARP. It still waits for the link and for the initial delay of service discovery, a random time (10 to 100 ms in the lab configuration) that keeps all ECUs from speaking at once. And it can be missed if the receiver is still booting, which is why offers are repeated.

The price is paid in the switch. It learns only from source addresses, and a multicast address is never a source. Without configured multicast tables, or IGMP snooping (the switch listens to who joins which group), it sends the frame to every port in the VLAN, also to the small zone ECU that doesn't need it.

Rules of thumb for the vehicle:

- **Multicast** for cyclic data with many receivers, such as vehicle speed or vehicle state, and for service offers.
- **Unicast** for few receivers, for large data such as a camera stream to one computer, and for commands and diagnostics.
- **Always with multicast:** static multicast tables in the switch, a VLAN per function class, and hardware filters in the ECU.

A command to exactly one receiver gains little from multicast: with a static ARP entry, unicast doesn't have to wait either, and it can't flood. A brake request that the brake *and* the rear zone with the lamp need is a different case.

| Vehicle data | Transport | Why |
|---|---|---|
| Wheel speed, brake request (cyclic) | UDP | The next value is newer than a repetition |
| Vehicle speed for ten consumers | UDP multicast | Sent once |
| Service offers | UDP multicast | Everyone must hear it after wake-up |
| Flashing, diagnostics | TCP | Nothing may be missing |
| Audio and video | Often AVTP, without IP | Presentation time and reserved bandwidth |

**What it means.** A repetition in TCP can cost 200 ms and more. At 100 km/h that's 5.6 m. So cyclic control data goes over UDP, and the safety argument comes from E2E protection (counter, CRC, timeout) in the payload. Keep UDP payloads at or below 1472 bytes, because a larger packet is fragmented, and one lost fragment destroys the whole radar object list. SOME/IP-TP splits it in a controlled way instead.

## SOME/IP: from signals to services

SOME/IP stands for Scalable service-Oriented MiddlewarE over IP.

**The analogy.** SOME/IP is the price list of a workshop: "service 7, oil change". You order by number, and both sides need the same list, because the order only says 7. You can also leave your number and be called when something changes.

**In detail.** A **service** has **methods** (call, maybe with a response), **events** (reported to subscribers) and **fields** (a value with getter, setter and notification). For a vehicle function it looks like this:

| Element | Lighting service | Brake service |
|---|---|---|
| Method | `SetAmbientColor()` | `GetPressure()` |
| Fire and forget | `FlashOnce()` | |
| Event | `LampFailure` | `PressureChanged` |
| Field | `HighBeamState` | `ForceLimit` |

The header has 16 bytes. In the lab exercise, with hand-built messages, the camera asks the brake for its pressure:

```
request   1001 0001 | 0000 0008 | 0002 0001 | 01 01 00 00
response  1001 0001 | 0000 000a | 0002 0001 | 01 01 80 00 | 00 c8
          service,    length      client,     versions,     200
          method                  session     type, code
```

The response copies service, method, client and session, which is how the caller matches it. There's no name and no type anywhere. `00 c8` is 200 only because both sides know that a `uint16` sits there. If a brake update changes it to `uint32` without raising the interface version, 200 becomes `00 00 00 c8`, a camera that still reads the first two bytes sees 0, and possibly nobody reports an error.

**What it means for the vehicle.**

- **The interface description is the contract**, and its version belongs to the architecture. A car gets updates for many years, ECU by ECU. Plan which versions may meet, or update them as one set.
- **SOME/IP repeats nothing.** Timeouts and substitute values belong in the function design: what does the instrument cluster show when the speed event stops?
- **Client IDs are unique in the vehicle.** That's a list somebody has to own.
- **In AUTOSAR Classic** it sits in `SomeIpXf`, `SoAd` and `Sd`. In Adaptive, it sits below `ara::com`. The same service can be served by an MCU today and by a partition in the central computer in the next model year, and that's the point.

## Service discovery

**The analogy.** Charging stations in a navigation system. A station announces: "I exist, I'm here, I have two free connectors." The entry is only valid for a while. If the station loses power, it doesn't say goodbye, its entry simply disappears. And whoever wants to be told about a free connector leaves an address.

**In detail.** The brake offers its service by multicast, including where it can be reached. The camera subscribes by unicast and includes **its own** address for the events. Both agreements have a **TTL** and must be renewed.

{% include anim.html src="/assets/videos/automotive-ethernet/service-discovery.mp4" alt="Sequence animation: the brake multicasts OfferService 0x1001 with a TTL of 3 seconds. The camera subscribes to event group 1, the brake acknowledges and sends two events. Then the brake is disconnected, the TTL counts down from 3 to 0, and the camera treats the service as gone." caption="No goodbye needed. Whatever isn't renewed expires." %}

| In the vehicle | How the client notices |
|---|---|
| ECU goes to sleep properly | Offer with TTL 0 ("StopOffer") |
| ECU fails, connector loose | TTL runs out |
| ECU restarts quickly (undervoltage while cranking) | Reboot flag and session counter start again |
| Option not installed, e.g. no trailer module | No offer ever arrives |
| Function moved to the central computer | Offer with a different endpoint |

**What it means for the vehicle.** Service discovery solves the start order, the variants and relocated functions, which is exactly what a software-defined vehicle needs. Three limits:

- **It takes time**, typically some hundred milliseconds after wake-up. Functions that have to work at once, such as exterior lighting or the brake light, use static endpoints. The reversing camera's AVTP stream doesn't use service discovery at all, its path is configured.
- **The TTL is not a safety mechanism.** A TTL of 3 s means 83 m at 100 km/h. It's fine for ambient light and useless for AEB, which needs the timeout of its E2E protection, in the range of a few cycles.
- **It believes everyone.** More on that in [Part 3]({% post_url 2026-11-24-automotive-ethernet-for-the-sdv-part-3-time-tsn-and-security %}).

## DoIP: the workshop entrance

**The analogy.** A dealership has one service desk. The door is locked until the customer rings. The customer shows the registration, gets a badge for one visit, and says: "Please ask the brake department." The desk passes it on and says "accepted". That only means the request is on its way: the brake department can still refuse it. And the customer never learns how the desk reached the department, by phone or on foot. They only need its name.

**In detail.** DoIP (Diagnostics over IP, ISO 13400) carries UDS (Unified Diagnostic Services, ISO 14229). The tester at the OBD connector sets the activation line, and only then does the gateway enable the Ethernet port. It finds the vehicle by UDP broadcast and gets the VIN and the logical address. Then it opens a TCP connection to port 13400 and activates routing for its own address.

<div class="mermaid">
sequenceDiagram
    participant T as Tester 0x0E00
    participant G as Gateway 0x1000
    participant B as Brake 0x1003 (CAN or Ethernet)
    T->>G: Vehicle identification request (UDP broadcast)
    G->>T: VIN, logical address 0x1000
    T->>G: TCP connect, routing activation "I am 0x0E00"
    G->>T: activated (0x10)
    T->>G: to 0x1003: 22 F1 90
    G->>T: DoIP ACK (accepted for delivery)
    G->>B: 22 F1 90
    B->>G: 62 F1 90 + VIN
    G->>T: from 0x1003: 62 F1 90 + VIN
</div>

**DoIP** is transport ("bring these bytes to 0x1003"), **UDS** is content ("read the DTCs"). In the lab exercise, with prepared responses, the brake refuses a programming session with `7F 10 22` (conditions not correct, for example because the vehicle is moving), and the tester still gets a positive DoIP acknowledgment. Both are right: delivered, and refused.

**What it means for the vehicle.**

- **Diagnostics survives the architecture change.** An ECU behind the gateway needs neither IP nor Ethernet. In consolidated compute, several former ECUs become partitions, and each can keep its logical address. Workshop and plant processes don't have to change with every step.
- **Speed is the reason it exists.** 100 Mbit/s at the connector against 500 kbit/s on classic CAN is a factor of 200 on paper, and still a factor of 50 against a CAN FD data phase of 2 Mbit/s. For computers with images of hundreds of megabytes, that decides whether the end of line keeps its cycle time. After that, writing the flash is often the limit. Check the slowest link behind the gateway too: an ECU on CAN is still flashed at CAN speed.
- **It's an entrance.** Activation line, routing activation, sessions, authentication and preconditions such as "vehicle standing still" are layers. Review them as one chain.

## Where this leaves us

An ECU can now find a neighbor, cross a VLAN boundary, use a service and be diagnosed. None of it is punctual yet, and all of it trusts whoever speaks. [Part 3]({% post_url 2026-11-24-automotive-ethernet-for-the-sdv-part-3-time-tsn-and-security %}) adds a common clock, guaranteed latency and distrust.

*Lab examples come from my own learning project. Animations: [manim](https://www.manim.community/), `scripts/manim/ethernet_scenes.py`.*
