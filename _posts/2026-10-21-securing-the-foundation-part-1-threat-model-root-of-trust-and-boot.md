---
layout: post
title: "Securing the Foundation, Part 1: Threat Model, Root of Trust and Boot"
date: 2026-10-21
categories: [Security]
tags: [security, tara, iso-21434, hsm, key-management, secure-boot, fault-injection, cortex-m7]
---

*This is Part 1 of a three-part series on embedded security for our BCU. This part covers the threat model, the root of trust and the boot concept; [Part 2]({% post_url 2026-10-21-securing-the-foundation-part-2-updates-bus-and-diagnostics %}) covers updates, the bus and diagnostics; [Part 3]({% post_url 2026-10-21-securing-the-foundation-part-3-code-debug-immobilizer-and-detection %}) covers the code, the debug port, the immobilizer, detection and privacy.*

*Quick recap of the BCU from the foundation series: [Part 1]({% post_url 2026-08-30-create-the-foundation-part-1-requirements-and-thinking %}) (requirements), [Part 2]({% post_url 2026-09-03-create-the-foundation-part-2-memory-mapping-and-partitioning %}) (memory map), [Part 3]({% post_url 2026-09-04-create-the-foundation-part-3-protection-allocation-and-cpu-load %}) (memory protection) and [Part 4]({% post_url 2026-10-19-create-the-foundation-part-4-swc-allocation-and-task-setup %}) (SWC allocation and tasks). If you haven't read them, the short version: six Cortex-M7 cores, one simplex ASIL B core for exterior lighting, five QM cores for everything else, an HSM with its own firewalled flash, and no A/B swap.*

In foundation Part 3, I hid a side note in the middle of the MPU chapter: *safety is not security, that's a post of its own.* Side notes like that are promises. This is me keeping one.

The difference fits in one sentence. Safety protects the car from its own mistakes. Security protects it from somebody who makes mistakes happen on purpose. A bit flip doesn't read your source code, doesn't wait for the one millisecond your check is skipped, and doesn't come back next week with a better tool. An attacker does all three. So everything we built in the foundation series (default-deny, E2E, mailboxes, watchdogs) is a good start, but it was designed against faults that are random and don't try to get past you.

The good news: if you followed the series, a lot of security is already there, just not labelled as such. The bad news: the rest touches nearly every part of the ECU, from the production line to the scrapyard. So let's go through it door by door, using our BCU. Every door gets the same three questions: what's behind it, who wants in, and what keeps them out. There are ten doors, which is too many for one post, so this is a three-part series. This part sets up the threat model and covers the two doors everything else depends on: the root of trust and the boot.

## Step zero: the TARA, or "who actually wants in?"

In safety you start with a HARA. In security you start with a TARA (threat analysis and risk assessment), as defined by ISO/SAE 21434. Since UN R155 came in, it's not optional anymore: no cybersecurity management system, no type approval, no car. That gets a project manager's attention very quickly.

A TARA works in five steps:

1. **Assets.** What's worth protecting, and which property of it: confidentiality, integrity or availability.
2. **Damage scenarios.** What happens if that property is lost, rated in four impact categories: safety, financial, operational and privacy.
3. **Threat scenarios and attack paths.** How someone gets there, step by step.
4. **Attack feasibility.** How hard that is: time, expertise, knowledge of the target, window of opportunity, equipment.
5. **Risk and treatment.** Impact × feasibility gives a risk value. For each risk you decide: reduce it, accept it, share it (insurance, contracts) or avoid it (drop the feature).

The output is a set of **cybersecurity goals**, and from those you derive requirements. Without a TARA, every security discussion turns into "but what if the attacker…" and never ends, because an attacker with enough budget can always do one more thing. The TARA is how you decide where to stop. It turns paranoia into a documented, reviewable risk acceptance. Paranoia is cheap, the documented version costs effort.

Here's a heavily trimmed first TARA for our BCU. As always in this series, the ratings are assumptions with a date on them, not results. If you want the untrimmed version — 14 assets, 13 damage scenarios, 19 threat scenarios with attack-potential ratings, risk treatment and eight cybersecurity goals with their CAL — it's in the repo as [`examples/TARA_BCU_example.xlsx`](https://github.com/Kuebelrobert/kuebelrobert.github.io/blob/main/examples/TARA_BCU_example.xlsx). Same idea as the memory map: the source of truth is a YAML file, [`_data/tara_bcu.yml`](https://github.com/Kuebelrobert/kuebelrobert.github.io/blob/main/_data/tara_bcu.yml), and [`scripts/build_tara.py`](https://github.com/Kuebelrobert/kuebelrobert.github.io/blob/main/scripts/build_tara.py) refuses to generate the workbook if a risk above the acceptance threshold is left untreated.

| Asset | Property | Damage scenario | Impact | Main attack path | Feasibility |
|---|---|---|---|---|---|
| Central locking / unlock command | Integrity | Car opened and stolen | Severe (financial) | Injecting frames on a body CAN or LIN reachable from outside (door, mirror, headlight harness) | High |
| Immobilizer secret | Confidentiality | Keys cloned, car started without an authorized key | Severe (financial) | Debug port, side-channel on the ECU, sniffing the immobilizer protocol | Medium |
| Brake / hazard light request | Integrity | Phantom brake lights, confused following traffic | Moderate (safety) | Spoofed CAN FD frames via OBD port or a compromised ECU | High without SecOC |
| Application firmware | Integrity, authenticity | Persistent malicious code in the ECU | Severe | Manipulated update package, debugger, rollback to a vulnerable version | Medium |
| SecOC and diagnostic keys | Confidentiality | Attacker can authenticate as any ECU on the bus | Severe | Shared keys extracted from one ECU and reused in the whole fleet | Medium |
| Diagnostic functions (IO control, write DIDs) | Integrity | Lamps switched, configuration changed, variant coding manipulated | Major | Weak UDS SecurityAccess, brute force | High |
| ECU availability | Availability | No lights, no doors | Major (safety, operational) | Bus flooding, update that bricks the ECU | High |
| Stored data (DTC snapshots, lock/unlock history) | Confidentiality | Movement and usage profile of the driver | Moderate (privacy) | Reading event memory over diagnostics | High |

The first row is my favorite, because it's not hypothetical. For a while, a popular way to steal cars was to pull out the headlight connector, plug a device into the CAN wires behind it and send "unlock" and "immobilizer OK". No hacking of the radio, no stolen key. Just the wiring harness, which runs to places on the outside of the car where anyone can reach it. For a BCU, which is the ECU attached to almost every one of those wires, this is the threat model in one picture.

Here's the whole attack surface of our BCU on one page: every way in from the outside, where it lands, and which door of this series deals with it. Keep it open in a second tab, all three parts refer back to it.

{% include security-attack-surface.html %}

Two more points before we go door by door:

- **Security doesn't replace safety goals, it adds new ones.** The brake light row is both a safety topic (HARA, ASIL B, foundation Part 4) and a security topic (TARA, SecOC). They need to agree. A security reaction that turns the brake light off "because the message was tampered with" is unsafe. Write down how the two interact, the same way foundation Part 3 wrote down the QM/ASIL failure behavior.
- **The TARA rates attackers with physical access too.** Someone who bought the same BCU at a scrapyard has unlimited time, a lab, and no reason to hurry. Whether you defend against them (fault injection, side channels) is a decision the TARA makes, not your gut feeling. Usually the answer is "protect the secrets that are shared across many vehicles, accept the rest". More on that later.

## Door 1: the root of trust — who checks the checker?

Every security mechanism in the ECU eventually rests on the question: who checked that the checker is genuine? At some point that chain has to stop at something you trust because it *can't* be changed. That is the root of trust.

In our BCU it's three things, and foundation Part 2 already gave each of them a place:

- **The HSM's boot ROM.** Mask ROM in silicon, burned at the chip factory. It verifies the HSM firmware before the HSM runs it.
- **The HSM firmware and its keys** in the firewalled HSM Flash (256 KB) and HSM Data Flash (32 KB). No application core can read them, not even the ASIL B one. That's not the MPU, that's the hardware firewall, and that's important: if a QM core gets compromised and runs privileged, the MPU is gone. The firewall isn't.
- **Stage-1**, the 64 KB bootloader that's `read-only` after production and has no update path. Paired with the HSM, it decides what runs next.

### What the HSM is actually for

The HSM is a separate core with its own memory, its own crypto accelerators and its own firewall. The application cores talk to it through a job interface: "compute a CMAC over this buffer with key slot 7" — and they get the result, never the key. The key never leaves the HSM in plaintext. That's the whole idea: **an application compromise must not mean a key compromise.** If an attacker gets code running on QM Core 5, they can ask the HSM for MACs as long as they're in, which is bad. But when they're out, they don't take the key with them, and the next update closes the hole. Once a key is extracted, no update helps.

{% include anim.html src="/assets/videos/embedded-security/hsm-job-interface.mp4" alt="Animation: Core 5 sends a CMAC job with key slot 7 to the HSM and gets a MAC back. A compromised core then tries to read key slot 7 directly and is blocked at the firewall. It can still request MACs while it is in, but after an update fixes it, the key is still inside the HSM." caption="Jobs go in, results come out. A direct read of the key hits the firewall, and after the fix the attacker leaves with nothing." %}

What our HSM provides, and who uses it in the BCU:

| HSM service | Used for | Called from |
|---|---|---|
| AES-128 CMAC generate/verify | SecOC, boot verification, immobilizer protocol | Core 1 (SecOC), Core 5 (immobilizer), Stage-1 |
| Signature verification (ECDSA, later post-quantum) | Update packages, diagnostic certificates | Stage-2, Core 5 (update manager, UDS 0x29) |
| Hash (SHA-256) | Update package hashing, boot verification | Stage-2, Stage-1 |
| True random number generator | Challenges (UDS, immobilizer), nonces, key generation | Core 5 |
| Monotonic counters | Anti-rollback, SecOC freshness | Stage-2, Core 1 |
| Secure key storage and key update | All of the above | HSM-internal |
| Secure debug unlock | Debug access in the field | HSM-internal |

The 32 KB "placeholder" in HSM Data Flash from foundation Part 2 now gets a first sizing: around 20 key slots with metadata, a few monotonic counters (wear-leveled, because counters that increment on every update or every ignition cycle *will* wear out a sector), two or three certificates of around 1 KB each, and the lifecycle state. 32 KB is enough, with room to spare. The placeholder just became a decision.

### The key inventory

You can't protect keys you didn't write down. This is the list I'd put into the architecture document, and the moment where most projects discover they have more keys than they thought:

| Key | Type | Scope | Stored in | Provisioned | Replaced by |
|---|---|---|---|---|---|
| Boot MAC key | AES-128 | Per ECU | HSM Data Flash | Generated in the HSM on first boot | Never (re-generated after an update) |
| Software signing key (OEM) | ECDSA public key | Per vehicle line | HSM Data Flash, or Stage-1 as a fallback | Production | Key update with a key-signing key |
| SecOC keys | AES-128 | Per bus cluster, per vehicle | HSM Data Flash | End of line, via the vehicle's key master | Authenticated key update protocol |
| Immobilizer secret | AES-128 | Per vehicle (pairing BCU ↔ keys ↔ engine ECU) | HSM Data Flash | End of line / workshop pairing | Workshop re-pairing (authenticated) |
| Diagnostic ECU identity | ECDSA key pair + certificate | Per ECU | HSM Data Flash | End of line | Certificate renewal over UDS 0x29 |
| Diagnostic root CA | ECDSA public key | Per OEM | HSM Data Flash | Production | Key update |
| Debug unlock key | AES-128 | Per ECU, derived | HSM Data Flash | Production | Never |
| TLS / DoIP keys | ECDSA key pair | Per ECU | HSM Data Flash | End of line | Certificate renewal |

The two rules behind that table:

- **No secret is shared across the fleet.** If a key is the same in every BCU, one BCU from a scrapyard, one side-channel attack and one weekend give you every car. Per-ECU keys are derived from a master key and the ECU serial number (from the ECU OTP block in foundation Part 2) in the key management backend. The master key never sees an ECU. The only things that are the same in every ECU are *public* keys, and those only need integrity, not confidentiality.
- **Every key has a way out.** Algorithms get broken, keys leak, certificates expire. For every key in the table, "how do we replace it in a car that's already in the field?" needs an answer before production starts. "We'll do a recall" is an answer, just a very expensive one.

## Door 2: boot — secure, authenticated, or just fast?

Foundation Part 1 already warned about this conflict: secure boot that checks megabytes of code before anything starts is great for security and terrible for "the bus expects an answer in 150 ms". Now we have the memory map, so we can do the math instead of worrying about it.

First, the terms, because people use them interchangeably and they aren't:

- **Secure boot:** each stage verifies the next one *before* it runs. If the check fails, the next stage doesn't run at all.
- **Authenticated boot:** the next stage starts immediately, and the check runs in parallel. If it fails, the system loses its privileges: the HSM refuses to hand out keys for this boot cycle, and the event gets reported.
- **Measured boot:** each stage records a hash of the next one, and someone else (a backend, a remote verifier) decides later whether to trust it. Common on PCs, rare on MCUs. I mention it so you've heard of it.

Now the numbers. Let's assume our HSM computes a CMAC at around 40 MB/s. That's an illustrative value — check your datasheet, the range across chips is huge. What we'd need to verify, using foundation Part 2's regions with realistic fill levels (only the image, not the reserved space):

| What | Size (actual image) | Verification time at 40 MB/s |
|---|---|---|
| Stage-1 | ~50 KB | ~1.3 ms |
| Stage-2 | ~200 KB | ~5 ms |
| ASIL B code + calibration | ~1.9 MB + ~0.4 MB | ~58 ms |
| QM code + calibration | ~6 MB + ~1.5 MB | ~190 ms |
| **Everything, strictly before start** | **~10 MB** | **~255 ms** |

255 ms just for verification, before any core has initialized a single CAN controller. With a 150 ms budget for the first answer on the bus, full secure boot simply doesn't fit. So here's what I'd do:

1. **The HSM boots first and verifies its own firmware** with its ROM. Strict, no exceptions.
2. **The HSM verifies Stage-1 before it releases the ASIL B core from reset.** Strict secure boot. 1.3 ms, nobody will notice.
3. **Stage-2 is verified strictly, but only when we actually enter it** (flashing session, or an invalid application). Normal startups don't pay for it.
4. **The applications use authenticated boot.** Stage-1 does the fast safety integrity check (more on that in a moment) and starts the cores. The HSM verifies the application images in the background. The SecOC keys, the immobilizer key and the diagnostic identity are **bound to the boot result**: the HSM only unlocks them for this power cycle after the verification succeeds, typically within 250–300 ms of reset.

{% include anim.html src="/assets/videos/embedded-security/boot-timeline.mp4" alt="Animation: two timelines from 0 to 300 ms with a bus deadline at 150 ms. Top: the HSM verifies about 10 MB before anything starts, the cores start at 255 ms and miss the deadline. Bottom: the HSM verifies Stage-1 in 1.3 ms, the cores start immediately and answer on the bus after about 80 ms, while the HSM verifies the applications in the background and unlocks the keys at about 258 ms." caption="Strict secure boot for everything misses the 150 ms deadline. Strict Stage-1 plus authenticated applications makes it, and the keys stay locked until the verification is done." %}

What an attacker gets from a manipulated application under this scheme: an ECU that runs, but can't send a single authenticated message, can't authorize the engine start and can't authenticate to a diagnostic tester. For the TARA, that's the trade-off to argue: for about a quarter of a second after each reset, unverified code runs, but it has no keys. And to get modified code into the flash at all, the attacker must already have defeated Stage-2's signature check or the debug lock. Those are doors 3 and 7, in [Part 2]({% post_url 2026-10-21-securing-the-foundation-part-2-updates-bus-and-diagnostics %}) and [Part 3]({% post_url 2026-10-21-securing-the-foundation-part-3-code-debug-immobilizer-and-detection %}). I'd accept that risk and write down why. If your TARA disagrees (for example, because the application controls an actuator that's dangerous even in that quarter second), the answer is strict verification for that part and a different startup concept, not "let's hope nobody tries".

Two things that make this cheaper than it looks:

- **Sign the image, not the region.** The 2 MB ASIL B region holds 1.9 MB of code. The signature covers the image length stored in the header, not the padding. Foundation Part 2's reserves cost memory, but not boot time.
- **Asymmetric at update time, symmetric at boot time.** Verifying an ECDSA signature takes a few milliseconds no matter the image size. Hashing the image is what costs time. So the update path (Stage-2) verifies the OEM signature once, and then the HSM computes a CMAC with the ECU's own boot MAC key and stores it. Every following boot checks only this CMAC, which is faster than re-checking the full signature chain and doesn't need the OEM's public key at runtime.

### Integrity for safety, authenticity for security

Foundation Part 2 left a caveat in the YAML: the check that stops a corrupted ASIL B image from starting is a *safety* mechanism against random hardware faults and probably needs ASIL B. The HSM's CMAC is a *security* mechanism, usually developed as QM.

It's tempting to say "the CMAC catches every bit flip anyway, so we just need one check". Technically true, but the safety case then rests on HSM firmware developed to a standard that doesn't fit. So in our BCU, Stage-1 runs a fast CRC over the ASIL B image, developed to ASIL B, *and* the HSM runs its CMAC. Two checks over the same bytes for two different reasons. It looks redundant, but it means neither the safety assessor nor the security assessor has to accept evidence from the other team's process. If you want to merge them, talk to both assessors first. Together, ideally — that's a meeting worth bringing popcorn to.

### Fault injection: the attack on the `if`

The most efficient attack on secure boot doesn't break the crypto. It skips the comparison. A short voltage glitch or an electromagnetic pulse at the right moment, and `if (result != OK)` takes the wrong branch. There's equipment for this that costs less than a decent oscilloscope.

If the TARA puts this attack in scope (for the immobilizer, it probably does), the code that evaluates the boot result looks a bit paranoid:

```c
#define BOOT_OK    0x3CA5965Au   /* no 0/1: a single glitched bit must not produce "OK" */
#define BOOT_FAIL  0xC35A69A5u

volatile uint32_t res = hsm_boot_status(IMG_APP_ASILB);

if (res != BOOT_OK) { boot_fail(); }
delay_random_cycles();                         /* the attacker has to hit twice, at an unknown time */
if (hsm_boot_status(IMG_APP_ASILB) != BOOT_OK) { boot_fail(); }
if (res != BOOT_OK) { boot_fail(); }            /* re-check: the compiler keeps it because of volatile */
start_core(CORE_ASILB, img_entry(IMG_APP_ASILB));
```

Non-trivial constants, double checks, random delays, `volatile` so the compiler doesn't "optimize" the paranoia away. Plus the hardware: many automotive MCUs have voltage and clock monitors that reset the chip on a glitch, and the HSM runs its own checks with its own countermeasures. It doesn't make fault injection impossible, it makes it slower and less reliable. Usually that's enough to make the attack not worth it.

## Where this leaves us

Two doors in, we have the base everything else stands on. A TARA tells us what's worth protecting and where to stop. The HSM keeps every key behind a firewall that even a compromised, privileged core can't get through. The key inventory says where each key comes from and how it gets replaced. And the boot concept fits into foundation Part 1's startup budget by making the keys, not the start, depend on the verification.

What we haven't covered yet is everything that tries to get *into* the ECU while it's running: new firmware, frames on the bus and a diagnostic tester asking for more rights than it should have. That's [Part 2]({% post_url 2026-10-21-securing-the-foundation-part-2-updates-bus-and-diagnostics %}). The code itself, the debug port, the immobilizer and noticing an attack follow in [Part 3]({% post_url 2026-10-21-securing-the-foundation-part-3-code-debug-immobilizer-and-detection %}).

## Sources and further reading

### Standards and specifications

- ISO/SAE 21434:2021 — Road vehicles — Cybersecurity engineering — the TARA method used in step zero.
- [UN Regulation No. 155 — Cyber security and cyber security management system](https://unece.org/transport/documents/2021/03/standards/un-regulation-no-155-cyber-security-and-cyber-security) — Annex 5 lists the threats a type approval expects you to have thought about.
- [NIST SP 800-38B: The CMAC Mode for Authentication](https://csrc.nist.gov/pubs/sp/800/38/b/upd1/final) — the MAC behind fast authenticated boot.
- [NIST FIPS 186-5: Digital Signature Standard](https://csrc.nist.gov/pubs/fips/186-5/final) — ECDSA for signed images.
- [NIST SP 800-193: Platform Firmware Resiliency Guidelines](https://csrc.nist.gov/pubs/sp/800/193/final) — root of trust, protection, detection and recovery.
- [AUTOSAR Classic Platform: Crypto Service Manager, R23-11](https://www.autosar.org/fileadmin/standards/R23-11/CP/AUTOSAR_CP_SWS_CryptoServiceManager.pdf) and [Key Manager, R23-11](https://www.autosar.org/fileadmin/standards/R23-11/CP/AUTOSAR_CP_SWS_KeyManager.pdf) — how application cores talk to the HSM and keys.
- [EVITA project](https://www.evita-project.org/) — the research project behind the full/medium/light HSM classes still used today.
- [MCUboot](https://docs.mcuboot.com/) and [Trusted Firmware-M](https://www.trustedfirmware.org/projects/tf-m/) — open-source references for secure boot and a root of trust on Cortex-M.

### Papers

- Hagai Bar-El et al.: [*The Sorcerer's Apprentice Guide to Fault Attacks*](https://doi.org/10.1109/JPROC.2005.862424), Proceedings of the IEEE 94(2), 2006 — the classic overview of glitching and why one `if` is not enough.

### Books

- David Ward, Paul Wooderson: *Automotive Cybersecurity: An Introduction to ISO/SAE 21434*, SAE International, 2021
- Catherine H. Gebotys: *Security in Embedded Devices*, Springer, 2010
- Jasper van Woudenberg, Colin O'Flynn: *The Hardware Hacking Handbook*, No Starch Press, 2021 — fault injection and side channels from the attacker's side.
- Christof Paar, Jan Pelzl: *Understanding Cryptography*, Springer, 2010 — AES, CMAC and ECC explained for engineers.
- Adam Shostack: *Threat Modeling: Designing for Security*, Wiley, 2014
- Ross Anderson: *Security Engineering*, 3rd ed., Wiley, 2020

*The animations in this post are rendered with [manim](https://www.manim.community/) from [`scripts/manim/security_scenes.py`](https://github.com/Kuebelrobert/kuebelrobert.github.io/blob/main/scripts/manim/security_scenes.py).*
