---
layout: post
title: "Security Vocabulary, Part 2: Keys, Hardware, Boot and the ECU"
date: 2026-11-01
categories: [Security]
tags: [security, glossary, hsm, key-management, secure-boot, secoc, uds, attacks, iso-21434, cheat-sheet]
---

*This is Part 2 of a two-part vocabulary for the "Securing the Foundation" series ([Part 1]({% post_url 2026-10-21-securing-the-foundation-part-1-threat-model-root-of-trust-and-boot %}), [Part 2]({% post_url 2026-10-21-securing-the-foundation-part-2-updates-bus-and-diagnostics %}) and [Part 3]({% post_url 2026-10-21-securing-the-foundation-part-3-code-debug-immobilizer-and-detection %})). [Part 1 of this vocabulary]({% post_url 2026-10-30-security-vocabulary-part-1-the-crypto-toolbox %}) explained the crypto building blocks with pictures. This part is the reference for everything around them in an ECU: attack words, keys, hardware, boot and update, bus and diagnostics, attacks, and process.*

If you came straight here: this is a lookup page, built from tables, and every table is meant to be read on its own. The crypto words (MAC, hash, signature, nonce, certificate) are explained in [Part 1 of this vocabulary]({% post_url 2026-10-30-security-vocabulary-part-1-the-crypto-toolbox %}). If you only have a minute, this is the whole of it:

| Tool | In one line | Part 1 |
|---|---|---|
| **Hash** | A keyless fingerprint of any data | [Tool 1]({% post_url 2026-10-30-security-vocabulary-part-1-the-crypto-toolbox %}#tool-1-the-fingerprint-hash-functions) |
| **MAC** (HMAC, CMAC) | A tag only key holders can make: integrity and authenticity | [Tool 2]({% post_url 2026-10-30-security-vocabulary-part-1-the-crypto-toolbox %}#tool-2-the-seal-only-key-holders-can-make-mac-hmac-cmac) |
| **Freshness** | A counter or challenge inside the MAC, so a recording is worthless | [Tool 3]({% post_url 2026-10-30-security-vocabulary-part-1-the-crypto-toolbox %}#tool-3-is-it-new-freshness-nonces-and-randomness) |
| **Encryption** (AES, AEAD) | Nobody else can read it | [Tool 4]({% post_url 2026-10-30-security-vocabulary-part-1-the-crypto-toolbox %}#tool-4-keeping-secrets-encryption) |
| **Signature** (ECDSA, RSA) | One party can create, everybody can check | [Tool 5]({% post_url 2026-10-30-security-vocabulary-part-1-the-crypto-toolbox %}#tool-5-one-creator-many-checkers-signatures) |
| **Key agreement, KDF** | Agree on a secret in public; one secret in, many keys out | [Tool 6]({% post_url 2026-10-30-security-vocabulary-part-1-the-crypto-toolbox %}#tool-6-agreeing-on-a-secret-in-public-diffie-hellman-and-kdfs) |
| **Certificate** | A public key tied to an identity by a trusted authority | [Tool 7]({% post_url 2026-10-30-security-vocabulary-part-1-the-crypto-toolbox %}#tool-7-whose-key-is-this-certificates) |

## 1. The words around an attack

### 1.1 Threat vocabulary

People mix these up constantly, usually in the same sentence:

| Term | Meaning | Example |
|---|---|---|
| **Asset** | Something worth protecting, with a property to protect | The unlock command (integrity) |
| **Threat / threat actor** | Something or someone who could cause damage | A thief, a researcher, a bored teenager with a CAN adapter |
| **Vulnerability / weakness** | A flaw that could be abused (**CWE** is the catalog of weakness types) | A missing length check |
| **Exploit** | A technique or code that abuses a vulnerability | A crafted UDS request |
| **Attack** | An exploit used for real, against a target | The crafted request, sent to a car |
| **Attack vector / attack path** | The route in, and the sequence of steps along it | OBD port → gateway → body bus |
| **Attack surface** | The sum of all places an attacker can interact with the system | Every connector, bus, radio and parser |
| **Trust boundary** | A line where data or control passes between parts with different trust | OBD port → gateway |
| **Risk** | Impact combined with attack feasibility | "Severe damage, medium effort" |
| **Zero-day** | A vulnerability that is being exploited before a fix exists (you had zero days to prepare) | The unpleasant Friday afternoon |
| **CVE / CVSS** | CVE is the public ID of a known vulnerability, CVSS is its severity score | "A CVE in our TCP/IP stack" |
| **Supply chain attack** | Compromise through a library, tool or supplier instead of the target itself | A poisoned third-party component |
| **Class break** | One successful attack that works on every unit | One extracted fleet-wide key |

"Class break" deserves a second look, because it drives half of the key management decisions later: the cost of an attack is paid once, the reward is collected per vehicle.

### 1.2 Principles you'll hear in every review

- **Defense in depth.** No single mechanism is trusted to hold. Layers, each assuming the one before it failed.
- **Least privilege / default deny.** Every piece of code and every user gets exactly the access it needs, and everything else is forbidden. Same idea as the MPU rules in the foundation series.
- **Kerckhoffs's principle.** A system must stay secure even if everything about it except the key is public. The opposite is "security through obscurity", of which the "secret" seed-to-key algorithm that turns out to be an XOR with a constant is the most popular embedded variant.
- **Fail-safe vs. fail-secure.** Fail-safe: on error, go to the state that harms nobody (lamp on, door open). Fail-secure: on error, go to the state that lets nobody in (door locked). They can point in opposite directions, and the design has to decide per function, in writing, before an attacker decides for you.
- **Safety vs. security.** Safety protects the car from its own mistakes (HARA, the hazard analysis; ASIL, the safety integrity level; E2E, the safety protection of signals). Security protects it from somebody who makes mistakes happen on purpose (TARA, the threat analysis; MAC; HSM, the hardware security module). Mechanisms from one world don't count as evidence in the other.

### 1.3 STRIDE: the mnemonic for threat categories

Used in threat modeling to ask "what could go wrong?" in a structured way. Each letter is an attack that violates one of the properties from Part 1:

| Letter | Threat | Violates | One-line example |
|---|---|---|---|
| **S** | Spoofing | Authenticity | Sending the brake ECU's CAN ID from the OBD port |
| **T** | Tampering | Integrity | Modifying the firmware image |
| **R** | Repudiation | Non-repudiation | "I never unlocked that car", with no log to prove otherwise |
| **I** | Information disclosure | Confidentiality | Reading the lock/unlock history over diagnostics |
| **D** | Denial of service | Availability | Flooding the bus, or an update that bricks the ECU |
| **E** | Elevation of privilege | Authorization | A workshop tester doing what only production may do |

## 2. Keys: the words around the secret

Keys are the one part of this whole subject that has to stay secret, which is exactly why they're the part that leaks most often.

| Term | Meaning |
|---|---|
| **Symmetric key / shared secret** | One key known to both sides (MAC, AES) |
| **Private key / public key / key pair** | Asymmetric: the private key is secret, the public key is not (and only needs integrity protection) |
| **Master key / derived key** | A key from which per-ECU or per-session keys are derived with a KDF |
| **Session key vs. long-term key** | A session key lives for one connection or one power cycle; a long-term key lives for the product |
| **KEK / key wrapping** | A *key-encryption key* encrypts other keys so they can be transported or stored outside the secure hardware |
| **Key slot / key ID** | A numbered place in the HSM where a key lives; software refers to the slot, never to the key |
| **Key provisioning / injection** | Bringing the key into the ECU, in production or at end of line |
| **Key rotation / update** | Replacing a key by a new one, in the field |
| **Key revocation** | Declaring a key untrustworthy so it's no longer accepted |
| **Key ceremony** | A scripted, witnessed procedure for creating or handling a root key |
| **Key extraction** | The attacker getting the key out of a device; the thing key storage exists to prevent |
| **Key inventory** | The written list of every key: type, scope (per fleet, per vehicle, per ECU), where it's stored, how it's provisioned and how it's replaced. The moment most projects discover they have more keys than they thought. |
| **Per-ECU key / key diversification** | Every unit gets its own key, derived from a master and the serial number, so an extracted key opens exactly one unit |

A **key lifecycle** is: generate, provision, use, update, revoke, destroy. The sentence to remember from Part 1 of the series: *every key needs a way out*. If "how do we replace this in a car that's already on the road?" has no answer, the answer is "recall", and that is an expensive answer.

Two rules cover most of key management. **No secret is shared across the fleet**: if every ECU holds the same key, one scrapyard unit and one weekend give you every car. The only things that are the same in every ECU should be *public* keys, which only need integrity, not confidentiality. And **one key, one purpose**: the boot key, the bus key and the immobilizer key are three keys.

## 3. Hardware: where the secrets live

The HSM is the tiny, paranoid roommate who keeps all your keys, does your crypto homework on request, and will never, under any circumstances, hand over the keys. That is the whole job description.

| Term | What it is | Why it matters |
|---|---|---|
| **Root of trust (RoT)** | The part of the system you trust because it *can't* be changed (or because you can't see how it could be). Everything else is verified by it, directly or through a chain. | At some point the question "who checks the checker?" has to end |
| **Boot ROM** | Mask ROM in the silicon, written at the chip factory | Can't be updated, but also can't be modified; the first link of the chain |
| **OTP / eFuse** | Memory that can be written once, bits only go one way | Lifecycle state, identity, fused keys or hashes |
| **HSM** (hardware security module) | A separate core with its own memory, crypto accelerators and firewall, reached through a job interface: "compute a CMAC with key slot 7", and you get the result, never the key | An application compromise must not mean a key compromise |
| **EVITA light / medium / full** | Three HSM classes from a research project: roughly symmetric-only, mid-range, and full with asymmetric crypto | Marketing uses these words loosely. Read the datasheet. |
| **SHE** (Secure Hardware Extension) | A small, older spec: AES-128 and CMAC with a fixed set of key slots | What "light" HSMs are built around |
| **Hardware firewall** | Access control enforced by hardware on the bus or memory, independent of the CPU's privilege level | Unlike the MPU, a compromised privileged core can't reconfigure it |
| **MPU** | CPU-side memory protection, configured by privileged software | Great against faults and against unprivileged code; privileged code can change it |
| **TrustZone-M** | Armv8-M's split into a secure and a non-secure world on the same core | Cheaper than an HSM, a weaker isolation. Not available on a Cortex-M7; Cortex-M23 and M33 have it. |
| **Secure element / TPM** | A separate chip for keys and crypto (common outside automotive ECUs) | Same idea as the HSM, a different place |
| **Crypto accelerator** | Hardware for AES, hash, ECC | Speed and constant-time behavior |
| **Monotonic counter** | A counter that can only go up, even across power loss | Anti-rollback and freshness |
| **Secure key storage** | Keys held in memory that software can't read | The point of the HSM |
| **Debug lock / secure debug unlock** | JTAG/SWD closed in the field; reopened only through an authenticated, per-ECU challenge-response | The debug port is the master key; the unlock decides who may have it |
| **ECU lifecycle state** | A one-way state (development, production, field, ...) kept in OTP | Keys and debug access depend on it |

Two lines from the series are worth repeating here. First: **the HSM is not the MPU**. If a core is compromised and runs privileged, the MPU is gone; the HSM firewall isn't. Second: the HSM protects keys, not the application. A compromised core can still *ask* the HSM for MACs while it's compromised. It just can't take the key with it when it leaves.

## 4. Boot and update

| Term | Meaning |
|---|---|
| **Chain of trust** | Each stage verifies the next one before handing over control, starting at the root of trust |
| **Secure boot** | The next stage only runs if its verification succeeds |
| **Authenticated boot** | The next stage starts immediately and is verified in parallel; on failure the system loses its privileges (keys stay locked) and reports the event |
| **Measured boot** | Each stage records a hash of the next one; someone else decides later whether to trust the result. Common on PCs, rare on MCUs. |
| **Image header / signature over the image** | Metadata (length, version, hardware ID) plus a signature that covers the actual image length, not the padding around it |
| **Boot MAC** | A CMAC over the image with an ECU-specific key, computed after the first full verification and used for the following fast boot checks |
| **Immutable bootloader** | A first-stage loader that can't be updated, by design, which means it must do as little crypto as possible itself |
| **Signed manifest** | The first part of an update package: target blocks, sizes, hashes per block, security version, target hardware, and a signature over all of it |
| **Anti-rollback / security version** | A version number separate from the software version, compared against a monotonic counter; it only goes up when a real vulnerability is fixed |
| **Downgrade / rollback attack** | Flashing an older, correctly signed version with a known vulnerability |
| **A/B (dual-bank) update** | Two slots: write the inactive one, swap when it's verified. Without it, an update erases the old image first, which changes the order of checks. |
| **Recovery mode** | A minimal fallback that can still receive an authenticated update when the main image is broken |
| **OTA** (over-the-air) | Software update over a wireless link |
| **UN R156 / ISO 24089** | The regulation for software update management systems, and the engineering standard behind it |
| **Uptane** | An open framework for securing OTA updates in vehicles, including rollback and freeze attacks |

## 5. Bus, network and diagnostics

| Term | Meaning |
|---|---|
| **SecOC** (Secure Onboard Communication) | AUTOSAR's PDU-level authentication: each secured PDU carries a truncated **freshness value** and a truncated **MAC** (usually AES-128 CMAC). Spoofing needs the key; replay fails on freshness. |
| **Freshness value** | A counter per PDU, of which only the lower bits are sent; the receiver reconstructs the full value |
| **Trip counter / reset counter** | A coarser counter distributed by a master ECU so that all ECUs resynchronize their freshness after a reset |
| **Replay attack** | Recording a valid message and sending it again later |
| **E2E protection** | AUTOSAR's CRC, sequence counter and timeout for **safety** against random faults on the communication path. Not security. |
| **CAN has no sender address** | The frame carries an ID, not a source. Anyone on the bus can send any ID, and that is the whole reason SecOC exists. |
| **LIN** | A slow, cheap bus with no security mechanisms; protection is architectural (never trust a slave for a security decision, plausibility checks, physical separation) |
| **Gateway** | Routes between buses and networks; a firewall whether you call it one or not |
| **Whitelist routing / stateful rules / rate limiting** | Only listed routes exist; rules depend on vehicle state and session; each source has a maximum frame rate |
| **MACsec** (IEEE 802.1AE) | Link-layer encryption and authentication on Ethernet, using AES-GCM |
| **TLS** | Transport-layer security: handshake with certificates and ECDH, then AEAD-protected data |
| **DoIP** (diagnostics over IP) | UDS over Ethernet, ideally protected with TLS |
| **OBD port** | The legally required diagnostic connector, reachable from the driver's seat by anyone. It's the front door of the attack surface, so everything behind it is treated as untrusted. |
| **UDS** (ISO 14229) | The diagnostic protocol. The security-relevant services: |
| ↳ **0x27 SecurityAccess** | Seed-and-key: the ECU sends a seed, the tester computes a key. Only as strong as the algorithm, the seed and the attempt limit behind it. |
| ↳ **0x29 Authentication** | Certificate-based tester authentication with roles (added to UDS in 2020) |
| ↳ **0x2E / 0x31 / 0x2F** | WriteDataByIdentifier, RoutineControl and InputOutputControl: the services that need authentication, because they change things |
| ↳ **0x10 DiagnosticSessionControl** | Sessions (default, extended, programming); authentication is bound to the session |
| ↳ **0x14 / 0x19** | ClearDiagnosticInformation and ReadDTCInformation |
| **Failed-attempt counter** | Counts wrong keys and delays the next attempt; it must survive a reset, or the attacker just power-cycles |
| **Role-based access** | Rights come from the roles in the tester's certificate (workshop, engineering, production), not from one shared secret |
| **Immobilizer** | A function where security isn't a protection, it *is* the function: the engine only starts if a legitimate key is present. Typically a challenge-response between key, BCU and engine control. |
| **Transponder / keyless entry key** | The key side of the immobilizer protocol: it answers a challenge with a MAC over a shared secret. Old proprietary ciphers in these have been broken in public, so check what the supplier actually delivers. |
| **Pairing** | Establishing the shared secret between key, BCU and engine ECU; only allowed through an authenticated procedure (end of line, workshop) |
| **Passive keyless entry (PKE)** | Unlocking and starting without touching the key. Convenient, and the reason relay attacks exist (see the next section). |

## 6. Attacks and what stops them

Most real attacks don't break the crypto. They go around it, usually through the part nobody reviewed.

| Attack | The idea | What stops it |
|---|---|---|
| **Spoofing** | Pretending to be another sender | MAC / signature with a key the attacker doesn't have |
| **Tampering** | Modifying data or code | Hash protected by MAC/signature, signed images, W^X |
| **Replay** | Sending a recorded valid message again | Freshness value, nonce, challenge |
| **Relay attack** | Extending the radio range between key and car so the protocol runs perfectly | Distance measurement: ultra-wideband ranging, time-of-flight. Crypto alone can't help. |
| **Man-in-the-middle** | Sitting between two parties and relaying (or altering) everything | Authenticated key agreement: certificates and signatures in the handshake |
| **Brute force** | Trying all keys, PINs or tags | Long keys, long tags, limits on failed attempts (stored in NVM) |
| **Downgrade / rollback** | Reinstalling an old, vulnerable but signed version | Anti-rollback counter |
| **Denial of service** | Flooding a bus, or bricking via a bad update | Rate limiting, hardware acceptance filters, verify before erase |
| **Privilege escalation** | A low-rights actor gets high rights | Least privilege, MPU, hardware firewall, role-based access |
| **Side-channel attack** | Reading a secret out of timing, power consumption (**SPA/DPA**) or electromagnetic emissions instead of breaking the math | Constant-time code, masking, hardened HSM implementation |
| **Fault injection (glitching)** | A voltage, clock or electromagnetic glitch makes the CPU skip an instruction, for example the `if` after the signature check | Glitch monitors, non-trivial constants, double checks, random delays |
| **Buffer overflow / memory corruption** | Input longer than the buffer overwrites neighboring memory or the return address | Length checks, MPU, W^X (no memory both writable and executable), stack canaries, guard regions |
| **DMA attack** | A peripheral with DMA (an Ethernet MAC following a corrupted descriptor, for example) writes straight into RAM and bypasses the MPU, so it's a path from outside the car into memory | A bus firewall that limits which memory each DMA master may touch, plus keeping parsers out of ISRs |
| **ROP** (return-oriented programming) | Chaining existing code snippets instead of injecting new code, which W^X doesn't stop | Control-flow integrity, shadow stacks, fewer privileged parsers |
| **Key extraction** | Pulling a key out of one device (a scrapyard unit, a lab) | Hardware key storage, per-ECU keys so the reward is one device |
| **Supply chain attack** | Compromising a library, tool or supplier | SBOM, signed dependencies, build integrity, advisories |
| **Cloning** | Copying an identity (a key, an ECU) | Per-device secrets, challenge-response, authenticated pairing |

The fault-injection row deserves the paranoid code from the boot post in the series: constants like `0x3CA5965A` instead of `0`/`1`, a second check after a random delay, and `volatile` so the compiler doesn't optimize your paranoia away.

## 7. Detection, privacy and the process around it

| Term | Meaning |
|---|---|
| **IDS** (intrusion detection system) | Notices attacks: rule-based (unexpected CAN IDs, frame rates, failed MACs) or anomaly-based |
| **IdsM** | AUTOSAR's Intrusion Detection System Manager: collects security events in the ECU, filters them and passes them to a central IDS |
| **Security event** | Something suspicious worth reporting, such as a failed SecOC verification, a rejected update or a failed authentication |
| **SOC / SecOps** | The security operations center: the people who read the fleet's events and find the campaign hiding in the noise |
| **Tamper-evident vs. tamper-proof** | Evident: you can tell it was altered (for example a CMAC on each log entry). Proof: it can't be altered. Only the first is realistic. |
| **Event-flood DoS** | Triggering a security event so often that logging wears out the data flash. The IDS must not become the attack vector. |
| **Personal data / GDPR** | Lock and unlock history with timestamps is personal data in many legal systems. Store only what you need, only as long as you need it, readable only by authenticated roles. |
| **TARA** | Threat analysis and risk assessment: assets, damage scenarios, threat scenarios and attack paths, attack feasibility, risk treatment |
| **Risk treatment** | Reduce it, accept it, share it (insurance, contracts) or avoid it (drop the feature) |
| **Cybersecurity goal / requirement** | What the TARA concludes must be protected, and the requirements derived from it |
| **CAL** | Cybersecurity Assurance Level (1 to 4): how rigorous the development activities for a goal must be |
| **ISO/SAE 21434** | The cybersecurity engineering standard for road vehicles: the security counterpart to ISO 26262 |
| **UN R155 / CSMS** | The regulation requiring a cybersecurity management system for type approval; also demands detection and response in the field |
| **SBOM** | Software bill of materials: the list of all components in your software, so "which cars contain the affected library?" has an answer |
| **PSIRT / incident response** | The team and the process for handling a reported vulnerability or an attack |
| **Penetration test** | A test by people who didn't build the system. Internal reviews find what you thought of, pentesters find what you didn't. |
| **Fuzzing** | Feeding a parser with large amounts of random or mutated input and watching for crashes |
| **Static analysis, MISRA C, CERT C** | Tools and rule sets that catch unsafe patterns in the code before it runs |
| **Key backend / signing server** | The data center side: HSMs, key ceremonies, access control, the question who may sign a release. Often a bigger project than the ECU side. |
| **End of support** | The date after which there are no more fixes for this product. Write it down; regulators will ask. |

## 8. The greatest hits of mistakes

Not all of them are from other people's projects.

1. **A hash next to the data it protects.** An attacker changes both. Protect the hash with a MAC or a signature.
2. **The same key in every device.** One unit from a scrapyard and a weekend later, you own the fleet. Derive per-ECU keys from a master that never leaves the backend.
3. **A MAC without freshness.** Authentic, intact, and replayed. A recorded unlock frame is a perfectly valid unlock frame.
4. **Nonce reuse.** CTR, GCM and ECDSA all fail catastrophically if a number that must be unique is repeated. Make uniqueness a property of the design, not a hope.
5. **`memcmp` on a MAC.** It leaks through timing. Use a constant-time compare, or let the HSM do the compare.
6. **A homemade "algorithm".** The XOR with a constant has a loyal fan base. It never survives the first reverse-engineered tester DLL.
7. **A weak random seed.** Same seed after every reset means same "random" numbers after every reset.
8. **The failed-attempt counter in RAM.** A delay in RAM isn't a delay, it's a power cycle.
9. **Erase first, verify later.** Anybody who can start a flash session can brick the ECU with random bytes. Verify before erasing.
10. **A CRC doing a MAC's job.** Or the other way round, a QM MAC used as the safety argument. Different mechanisms for different enemies.
11. **No way out.** Keys and algorithms that cannot be replaced in a deployed vehicle are a recall waiting for a trigger.
12. **Encrypted is not signed.** Encrypting a firmware image keeps it private. It doesn't keep it from being replaced.

## Closing

Between the two parts, the vocabulary has one thread: a security design is a list of decisions about *who is allowed to do what, how an ECU can tell, and what happens when it can't*. The crypto in [Part 1 of this vocabulary]({% post_url 2026-10-30-security-vocabulary-part-1-the-crypto-toolbox %}) is the how, and this part is the where. If a term in the [Securing the Foundation]({% post_url 2026-10-21-securing-the-foundation-part-1-threat-model-root-of-trust-and-boot %}) series still feels vague, this page is the place to come back to, and if one is missing, tell me, and it will be there next time.

## Sources and further reading

### Standards and specifications

- ISO/SAE 21434:2021 — Road vehicles — Cybersecurity engineering
- [UN Regulation No. 155](https://unece.org/transport/documents/2021/03/standards/un-regulation-no-155-cyber-security-and-cyber-security) and [UN Regulation No. 156](https://unece.org/transport/documents/2021/03/standards/un-regulation-no-156-software-update-and-software-update)
- ISO 24089:2023 — Road vehicles — Software update engineering
- ISO 14229-1:2020 (UDS) and IEEE 802.1AE (MACsec)
- [AUTOSAR Classic Platform: Secure Onboard Communication, R23-11](https://www.autosar.org/fileadmin/standards/R23-11/CP/AUTOSAR_CP_SWS_SecureOnboardCommunication.pdf), [Crypto Service Manager, R23-11](https://www.autosar.org/fileadmin/standards/R23-11/CP/AUTOSAR_CP_SWS_CryptoServiceManager.pdf) and [Intrusion Detection System Manager, R23-11](https://www.autosar.org/fileadmin/standards/R23-11/CP/AUTOSAR_CP_SWS_IntrusionDetectionSystemManager.pdf)
- [NIST SP 800-193: Platform Firmware Resiliency Guidelines](https://csrc.nist.gov/pubs/sp/800/193/final) — root of trust, protection, detection and recovery.
- [EVITA project](https://www.evita-project.org/) and [Uptane](https://uptane.org/)

### Books

- Adam Shostack: *Threat Modeling: Designing for Security*, Wiley, 2014. Where STRIDE comes from.
- David Ward, Paul Wooderson: *Automotive Cybersecurity: An Introduction to ISO/SAE 21434*, SAE International, 2021
- Craig Smith: *The Car Hacker's Handbook*, No Starch Press, 2016. CAN, UDS and firmware updates from the attacker's side.
- Jasper van Woudenberg, Colin O'Flynn: *The Hardware Hacking Handbook*, No Starch Press, 2021. Side channels and fault injection from the attacker's side.
- Ross Anderson: *Security Engineering*, 3rd ed., Wiley, 2020
- Catherine H. Gebotys: *Security in Embedded Devices*, Springer, 2010
