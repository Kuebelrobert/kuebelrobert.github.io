---
layout: post
title: "Security Vocabulary, Part 1: The Crypto Toolbox for People Who Don't Do Crypto"
date: 2026-10-30
categories: [Security]
tags: [security, glossary, cryptography, mac, hmac, cmac, aes, ecdsa, diffie-hellman, certificates, beginner]
---

<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>mermaid.initialize({ startOnLoad: true, theme: "dark" });</script>

*This is Part 1 of a two-part vocabulary for the "Securing the Foundation" series ([Part 1]({% post_url 2026-10-21-securing-the-foundation-part-1-threat-model-root-of-trust-and-boot %}), [Part 2]({% post_url 2026-10-21-securing-the-foundation-part-2-updates-bus-and-diagnostics %}) and [Part 3]({% post_url 2026-10-21-securing-the-foundation-part-3-code-debug-immobilizer-and-detection %})). This part explains the crypto building blocks, from zero, with pictures. [Part 2]({% post_url 2026-11-01-security-vocabulary-part-2-keys-hardware-and-the-ecu %}) is the reference for everything around them in an ECU: keys, hardware, boot, bus, attacks and process.*

Security meetings have a failure mode I know well. Someone says "we'll just add a MAC", half the room nods, and the other half quietly wonders whether that's the thing in the Ethernet frame. (It isn't. Not here. MACsec manages to use both meanings in one protocol, which feels unfair.) In this post, **MAC always means message authentication code**, and by the end you'll know what it does, what it doesn't, and why people keep asking about the key.

This is written for the second half of that room: embedded engineers who are good at C, buses and timing, and who were never forced to learn what a hash is. No proofs, no number theory. (The index page of this blog promises "war stories, not tutorials". Consider this the one exception, and a war story needs a map.) If you already know the crypto, jump to [the cheat sheet](#the-toolbox-on-one-page) at the end and come back when something looks suspicious.

**The five-line version, if you read nothing else:** a **hash** is a fingerprint of data, with no key. A **MAC** is a fingerprint that only key holders can make, like a wax seal. A **counter or challenge** inside the MAC makes it single-use. A **signature** is a seal that one party can create and everybody can check. **Encryption** hides the content, and none of the others do. Everything below is the detail, the pictures, and the ways it goes wrong.

## The story: a key fob, a car and an attacker

Every tool in this post exists because somebody did something nasty to somebody else. So instead of a list of definitions, we'll follow one story, and add one tool whenever the story hits a hole.

The cast:

- **The key fob** sends a message by radio: `UNLOCK`.
- **The car** (in our series, an ECU, short for electronic control unit: one of the many small computers a car is full of) receives it and opens the door, if the message is genuine.
- **The attacker** stands in the parking lot with a laptop and a radio receiver. Security texts traditionally give this role a first name (Mallory, from "malicious"); we'll just call it the attacker.

{% include crypto-fig.html fig="cast" caption="Our whole story in one picture: the fob talks, the car listens, and the attacker hears everything on the way. Every tool in this post answers one of its moves." %}

What can the attacker do? The usual assumption is *a lot*, except for breaking into the fob's chip. They can **listen** to every message, **record** them, **replay** them later, **forge** their own messages, and **change** messages on the way. That's a normal attacker model for a car, because radio and bus wiring are public places. The wiring harness that goes into a door is as public as a radio signal, it's just slower to reach.

Here's the roadmap. Each row is one of the attacker's moves, and the tool that answers it:

| Round | What the attacker does | What we need | The tool | Section |
|---|---|---|---|---|
| 0 | Nothing yet, but we need a way to talk about data | A fingerprint of data | Hash function | [Tool 1](#tool-1-the-fingerprint-hash-functions) |
| 1 | Sends their own `UNLOCK` | Proof that the sender knows a secret | MAC (HMAC, CMAC) | [Tool 2](#tool-2-the-seal-only-key-holders-can-make-mac-hmac-cmac) |
| 2 | Records a genuine `UNLOCK` and plays it later | Proof that the message is new | Counter, nonce, challenge | [Tool 3](#tool-3-is-it-new-freshness-nonces-and-randomness) |
| 3 | Reads what's sent (a secret, a diagnostic result) | Nobody else can read it | Encryption (AES, AEAD) | [Tool 4](#tool-4-keeping-secrets-encryption) |
| 4 | Forges *firmware*, where one maker must create and millions of cars must check | Verify without being able to forge | Signature (ECDSA, RSA) | [Tool 5](#tool-5-one-creator-many-checkers-signatures) |
| 5 | Sits between two parties who have never met | Agree on a secret in public | Key agreement (Diffie-Hellman) and key derivation | [Tool 6](#tool-6-agreeing-on-a-secret-in-public-diffie-hellman-and-kdfs) |
| 6 | Hands over *their own* public key and claims it's the manufacturer's | Proof that a key belongs to who it says | Certificates | [Tool 7](#tool-7-whose-key-is-this-certificates) |
| 7 | Waits 15 years for a quantum computer | An exit plan | Post-quantum crypto, crypto agility | [Tool 8](#tool-8-the-quantum-footnote-and-the-exit-plan) |

Before the tools, one more thing: the questions a message has to answer.

### Six questions, with everyday pictures

Security people talk about *properties* of data. Here are the six that matter in a car, with a picture from a world without ECUs:

| Property | The question it answers | Everyday picture | In an ECU |
|---|---|---|---|
| **Authenticity** | Who really sent this? | A signature on a letter, or caller ID you can't fake | A frame from a genuine ECU, firmware from the real manufacturer |
| **Integrity** | Was it changed on the way? | The safety seal on a jar lid | A firmware image, a light request |
| **Freshness** | Is it new, or recorded earlier? | The date on the milk. A perfectly sealed carton of expired milk is still expired. | A replayed unlock command |
| **Confidentiality** | Can someone read it who shouldn't? | A sealed envelope instead of a postcard. Radio is a postcard. | An immobilizer secret, a lock/unlock history |
| **Availability** | Does it still work when someone is attacking it? | The door opens when you need it. A car that bricks itself on every attack is secure the way a paperweight is secure. | An ECU under bus flooding |
| **Non-repudiation** | Can the sender later deny having done it? | A notarized signature | A signed release, a signed certificate |

Authenticity, integrity, freshness and confidentiality are what most of this post is about. Confidentiality, integrity and availability together are the famous **CIA triad**. Freshness is the one people forget, and in a car it's the one that bites hardest: a recorded unlock frame is perfectly authentic, perfectly intact, and perfectly worthless to trust.

One more distinction that will keep coming back: **safety protects the car from its own mistakes, security protects it from somebody who makes mistakes happen on purpose**. Tools from the first world (CRC, watchdogs, E2E) don't count in the second, and we'll see exactly why in the cheat sheet.

## Tool 1: The fingerprint (hash functions)

**The problem it solves:** none, yet. A hash is the ingredient inside nearly everything else, so we start here.

**The picture:** a smoothie blender. Put in anything, whether a single strawberry or a whole crate of fruit, and you always get exactly one glass of smoothie. You can make a smoothie from fruit, but you can't make fruit from a smoothie. And the same fruit in the same amounts always gives the same smoothie.

A **hash function** (SHA-256, SHA-3) takes input of any size and produces a **digest**, a fixed-size fingerprint: 32 bytes for SHA-256. Always 32 bytes, whether the input is one word or six megabytes of firmware.

{% include crypto-fig.html fig="hash" caption="Any input, a same-size fingerprint, and no way back. The three digests are real SHA-256 values, shortened here." %}

Two properties make it useful. First, **one flipped bit in the input changes the digest completely**. Here are two real unlock commands that differ by one character:

```text
SHA-256("UNLOCK DOOR 1") = d59ad289f6a8db64d751f46bee48106734d50721268c580cd98fbe278a4e7bc6
SHA-256("UNLOCK DOOR 2") = 364c461a39507a0a2923216ba3af4a6f49aa0175d40a07772b27d6cfe8d464a7
135 of the 256 output bits differ: about half, as if somebody flipped a coin for every bit
```

This is called the **avalanche effect**, and it's what makes a hash a good fingerprint: you can't tweak your way from one input toward another, there's nothing to climb.

Second, it's **one-way** and **collision-resistant**. In plain words: from a digest you can't recover an input (**preimage resistance**), and you can't find two different inputs with the same digest (**collision resistance**). For an n-bit digest, finding a collision takes about 2^(n/2) work, which is why SHA-256 is described as "128-bit collision resistance". Old hash functions like MD5 and SHA-1 have practical collision attacks; finding one in an update path is a finding, not a style issue.

**What a hash does not give you: a lock.** A hash has no key, so everybody can compute it, including the attacker. If the fingerprint travels with the data, the attacker changes the data and computes a new fingerprint. A hash stored next to the data it protects is a tamper seal printed by the person you were worried about. It becomes useful when something protects the *hash itself*: a signature over it, a MAC, or a read-only memory location.

**Where it shows up in an ECU:** the fingerprint of an update block, the input of a signature (you sign the hash, not the 6 MB image), the core of HMAC and of key derivation.

**Words you'll hear:** digest, SHA-256, SHA-3, preimage, collision, avalanche effect, one-way function.

## Tool 2: The seal only key holders can make (MAC, HMAC, CMAC)

**The problem it solves:** the attacker sends their own `UNLOCK`. The car has no way to tell the difference.

**First idea, and why it fails:** put a password into the message: `UNLOCK, password=1234`. The attacker hears the message once. From then on the attacker knows the password. A secret that travels in the open is not a secret anymore.

**Better idea:** don't send the secret, send *proof that you know it*. That's a **message authentication code**, or **MAC**. The picture is a wax seal with a stamp that only you and the receiver own. The message is readable by everybody, but only someone with the stamp can make a seal that matches.

{% include crypto-fig.html fig="mac" caption="A MAC is the wax seal only key holders can make. The tag is the seal. The attacker can write a message, but not a seal that matches." %}

### How it works

1. Fob and car share a secret key `K`. (How they got it is a long story, see Tool 6 and [Part 2]({% post_url 2026-11-01-security-vocabulary-part-2-keys-hardware-and-the-ecu %}).)
2. The fob computes a **tag** from the message and the key: `tag = MAC(K, message)`, and sends `message ‖ tag`. (`‖` just means "followed by".)
3. The car computes the same thing from the message it received and its own copy of `K`, and compares the result with the received tag.
4. If they match, the message is unchanged and was made by someone who holds `K`. If not, it's dropped.

The tag is short, typically 8 to 16 bytes, and looks like random noise. Without the key, producing a matching tag for a new message is infeasible, and changing even one bit of the message changes the correct tag completely (the same avalanche effect as above).

### What a MAC gives you, and what it doesn't

| It gives you | It doesn't give you |
|---|---|
| **Integrity:** the message wasn't changed | **Confidentiality:** the message travels in plain text. A MAC protects, it doesn't hide. |
| **Authenticity:** it came from a key holder | **Non-repudiation:** both sides hold `K`, so the car could have made the tag too |
| | **Freshness:** a valid message with a valid tag stays valid forever (see Tool 3) |

### HMAC: a MAC built from a hash function

**HMAC** (RFC 2104) makes a MAC out of any hash function, usually SHA-256. If your chip has a hash accelerator but no AES, or you're writing software on a server, this is the one.

In plain words: HMAC mixes the key into the message, hashes, mixes the key in *again*, and hashes the result. Two nested hashes, with the key at both levels:

```text
K'  = K padded with zeros to the hash block size (64 bytes for SHA-256);
      a longer key is hashed first
ipad = 0x36 repeated, opad = 0x5C repeated (block size long)

HMAC(K, m) = H( (K' ⊕ opad) ‖ H( (K' ⊕ ipad) ‖ m ) )          ⊕ = XOR
```

Why twice? Because the obvious version, `H(K ‖ m)`, has a hole. SHA-2 and its older relatives process data in chunks, and the digest they output is the internal state after the last chunk. Anyone who knows `H(K ‖ m)` and the length of the key can feed that state back in and compute the hash of `K ‖ m ‖ padding ‖ extra stuff` (the padding being whatever the hash added on its own) **without knowing K**. It's like adding a paragraph to a sealed letter and re-sealing it with the old seal's imprint. This is called a **length-extension attack**, and the second, outer hash in HMAC closes it. The rule: **never build your own MAC by hashing key and message together.** Someone has already done that before you, and wrote a paper about it.

### CMAC: a MAC built from a block cipher

**AES-CMAC** (NIST SP 800-38B) makes a MAC out of AES. This is the one automotive lives on: SecOC, boot verification and HSM jobs almost always mean AES-128 CMAC, because every automotive HSM has AES in hardware, and CMAC only needs the "encrypt" direction.

In plain words: scramble the first block of the message with AES, mix the result into the second block, scramble again, and so on. The last scrambled block is the tag. Every block depends on all the blocks before it, so changing anything changes the end.

<div class="mermaid">
flowchart LR
    M1["Block 1"] --> X1(("⊕"))
    Z["zero IV"] --> X1
    X1 --> E1["AES with K"]
    E1 --> X2(("⊕"))
    M2["Block 2"] --> X2
    X2 --> E2["AES with K"]
    E2 --> X3(("⊕"))
    M3["Last block ⊕ K1<br/>(or padded, ⊕ K2)"] --> X3
    X3 --> E3["AES with K"]
    E3 --> T["Tag<br/>(truncated if the frame is small)"]
</div>

Plain chaining like this is called CBC-MAC, and by itself it's only safe if all messages have the same length (otherwise an attacker can splice two valid messages together into a third). CMAC fixes that by XORing the **last block** with one of two **subkeys**, `K1` or `K2`, which are derived from the key by encrypting a block of zeros. `K1` is used if the last block is complete, `K2` if it needed padding. That one trick makes CMAC safe for messages of any length.

### The MAC family

| Name | Built from | Tag size | Needs | Typical home |
|---|---|---|---|---|
| **HMAC-SHA-256** | A hash function | 256 bit (truncatable) | A hash; software is fine | TLS, tokens, key derivation |
| **AES-CMAC** | The AES block cipher | 128 bit (truncatable) | AES, ideally in hardware | SecOC, boot MAC, HSM jobs |
| **GMAC / GCM** | AES plus multiplication in a Galois field | 128 bit | AES and a **unique nonce** | MACsec (Ethernet), TLS |
| **Poly1305** | A one-time authenticator, paired with ChaCha20 | 128 bit | A unique key per message | TLS on cores without AES hardware |

### Try it yourself

This is real. Run it, change one character in the message, and watch the tag change completely:

```python
import hashlib, hmac
from cryptography.hazmat.primitives.cmac import CMAC
from cryptography.hazmat.primitives.ciphers import algorithms

key = bytes(range(16))        # a toy key: 00 01 02 ... 0f. Never use a key like this for real.
msg = b"UNLOCK|41"            # command, then a counter (more on that in Tool 3)

tag = hmac.new(key, msg, hashlib.sha256).digest()[:8]    # HMAC-SHA-256, cut to 8 bytes
print(tag.hex())                                          # 6db337fc2adfa882

c = CMAC(algorithms.AES(key)); c.update(msg)
print(c.finalize()[:8].hex())                             # 935cb33810b4f0ac  (AES-CMAC, 8 bytes)
```

Change `41` to `99` and the HMAC tag becomes `50c1c00cc30b763a`. That is the correct tag for `UNLOCK|99`, and nobody can compute it without the key. The attacker's only option is to guess.

### How long should a tag be?

A forger without the key guesses a tag of *t* bits right with probability 2^-t per try. At 128 bits that's never. At 64 bits, a common choice on a CAN FD frame, it's 1 in 18 quintillion per attempt. At 24 bits on a small classic CAN frame, the whole space of tags can be tried in well under an hour at full bus speed. A **truncated MAC** saves bytes on the bus and costs forgery resistance, and the rule is: the shorter the tag, the stricter the limit on failed verifications, because someone has to be counting the failures.

### Two practical rules

**Compare tags in constant time.** `memcmp` stops at the first byte that differs, and how long it took tells an attacker how many leading bytes of a guessed tag were right. That turns one huge guessing problem into eight small ones:

```c
/* Not memcmp: it leaks how many bytes matched through the execution time. */
static bool tag_equal(const uint8_t *a, const uint8_t *b, size_t n)
{
    uint8_t diff = 0u;
    for (size_t i = 0u; i < n; i++) { diff |= (uint8_t)(a[i] ^ b[i]); }
    return diff == 0u;
}
```

Better still: let the HSM do the verification, so the comparison happens inside and your code only gets a yes or a no.

**One key, one purpose.** The boot MAC key, the bus key and the immobilizer key are three keys. A key used for two things is a key whose compromise costs two things.

**Words you'll hear:** MAC, tag, HMAC, CMAC, GMAC, truncated MAC, length extension, constant-time compare.

## Tool 3: Is it new? (freshness, nonces and randomness)

**The problem it solves:** the attacker doesn't need to forge anything. They record a genuine `UNLOCK ‖ tag` while you lock your car, and replay it when you leave. The message is authentic, it's intact, the tag is valid. And it's worthless to trust.

**The picture:** a cinema ticket. It's genuine, but it's valid for one seat at one show, and the usher tears it. A MAC proves *who made* a message, not *when*.

There are two ways to make a message valid only once:

- **A counter.** The sender includes a number that goes up with every message (`UNLOCK|41`, then `UNLOCK|42`). The number goes *into the MAC*, so the attacker can't change it. The receiver remembers the last number and rejects anything not newer. Cheap, but both sides have to keep their counters in sync, also across power cycles. (In the automotive bus world, this is the **freshness value**, covered in [Part 2]({% post_url 2026-11-01-security-vocabulary-part-2-keys-hardware-and-the-ecu %}).)
- **A challenge.** The receiver asks a fresh question each time, and the sender's answer depends on it. Nothing to synchronize, but it needs a round trip. This is also called **challenge-response**, and it's the picture of a secret handshake where the other side asks for a different secret gesture every time.

<div class="mermaid">
sequenceDiagram
    participant S as Sender (has K)
    participant A as Attacker (no K)
    participant R as Receiver (has K)
    S->>R: m ‖ freshness 41 ‖ tag = MAC(K, m ‖ 41)
    R->>R: recompute tag, compare, check that 41 is newer than the last one
    Note over R: accepted, last freshness is now 41
    A->>R: replay of the recorded m ‖ 41 ‖ tag
    Note over R: tag is valid, but 41 is not newer than 41, so it is dropped
    A->>R: m' ‖ 99 ‖ guessed tag
    Note over R: tag does not match, so it is dropped
</div>

The same idea as a challenge-response. It shows up in the immobilizer (the function that only lets the engine start for a genuine key), in diagnostics and in debug unlock:

<div class="mermaid">
sequenceDiagram
    participant V as Verifier (e.g. ECU)
    participant P as Prover (e.g. tester or key)
    V->>P: challenge = fresh random value from the TRNG
    P->>V: response = MAC or signature over the challenge
    V->>V: verify the response against the challenge it just sent
    Note over V,P: a recording of an old response does not match the new challenge
</div>

### Numbers with a purpose

Security specs are full of numbers that are "random", "unique", "fresh" or "unpredictable". They are not the same thing, and mixing them up is a classic way to break a design:

| Name | Picture | Must be | Doesn't need to be | Used for |
|---|---|---|---|---|
| **Key** | The house key | Secret and random | Anything else | Everything |
| **Nonce** (number used once) | A ticket number | Unique for this key | Secret, sometimes even random | Encryption modes, replay protection |
| **IV** (initialization vector) | The starting position of the scrambler | Unique; for some modes also unpredictable | Secret | Block cipher modes |
| **Challenge** | The usher's question | Unpredictable and fresh | Secret | Challenge-response |
| **Freshness value** | The cinema's ticket counter | Monotonic: never repeats, never goes back | Secret or random | Bus authentication |
| **Salt** | A pinch of extra input | Unique | Secret | Key derivation, hashing |

### Where does randomness come from?

Challenges and keys need numbers nobody can guess. A **TRNG** (true random number generator) measures physical noise: think of rolling real dice. A **PRNG / DRBG** (deterministic random bit generator) is a long, pre-written list of dice rolls, and the **seed** tells it which line to start reading at. That works great if the starting line is random. **Entropy** is the amount of real unpredictability in the seed, and a DRBG can never be more unpredictable than its seed.

The classic embedded failure: a PRNG seeded with the same value after every reset starts at line 1 of the list after every reset, so it produces the same "random" sequence after every reset. The attacker needs a power switch. (Seeding from the uptime counter is the same bug with extra steps, because after a reset the uptime is also nearly the same.)

**Words you'll hear:** replay attack, freshness, counter, nonce, IV, challenge-response, TRNG, PRNG, DRBG, seed, entropy, salt.

## Tool 4: Keeping secrets (encryption)

**The problem it solves:** the attacker reads what's sent. A MAC doesn't help: it protects against changes, not against eyes.

**The picture:** radio is a postcard, anybody on the way can read it. Encryption is the sealed envelope with a lock.

**Symmetric encryption** uses one key to lock and the same key to unlock. It's the padlock with identical keys for fob and car:

{% include crypto-fig.html fig="keys" caption="One key for both sides (symmetric, left) versus a key pair with a public slot and a private key (asymmetric, right). We'll use the right-hand picture in Tool 5." %}

**AES** is the standard cipher. It scrambles exactly 16 bytes at a time, under a key of 128, 192 or 256 bits, and it's fast, small and in hardware on every automotive chip. But 16 bytes isn't a message. How you chain blocks to encrypt something longer is the **mode of operation**, and the mode matters much more than people expect. Here's the proof.

I took a picture of a padlock (a few flat colors, 192 by 192 pixels) and encrypted its raw pixel bytes with the *same* AES-128 key, once in a mode called ECB and once in a mode called CTR. Then I displayed the encrypted bytes as an image again:

<figure style="margin:1.5rem 0">
<img src="{{ '/assets/images/security-vocabulary/ecb-demo.png' | relative_url }}" alt="Three images side by side: an original padlock picture, the same picture encrypted with AES in ECB mode where the padlock outline is still clearly visible in the colored stripes, and the same picture encrypted with AES in CTR mode which looks like random noise." style="width:100%;max-width:760px;height:auto;display:block;margin:0 auto;border-radius:6px">
<figcaption style="font-size:0.9rem;margin-top:0.5rem">Same key, same cipher, same data. In ECB mode, equal input blocks give equal output blocks, so the padlock shines through the encryption. In CTR mode, it's noise. (Generated with [`scripts/ecb_demo.py`](https://github.com/Kuebelrobert/kuebelrobert.github.io/blob/main/scripts/ecb_demo.py) from this blog's repo: real AES, not a mock-up.)</figcaption>
</figure>

ECB encrypts every 16-byte block on its own, so a big flat blue area becomes a big flat area of *one* encrypted block, repeated. The picture is perfectly "encrypted", and you can still see the padlock. That's why you don't use ECB. (If a vendor's SDK offers ECB as the default, that's not a feature, that's a conversation.) The other modes you'll meet:

| Mode | In plain words | The gotcha |
|---|---|---|
| **ECB** | Every block on its own | Patterns survive, as the padlock shows. Never use it. |
| **CBC** | Each block is mixed with the previous encrypted block first; needs an **IV** and padding | The IV must be unpredictable. No integrity: flipped bits in the ciphertext flip bits in the next plaintext block. Padding errors have a long history of leaking data. |
| **CTR** | AES scrambles a counter, the output is XORed onto the data (a stream cipher) | A (key, nonce) pair must **never** repeat. Twice gives the attacker the XOR of both plaintexts, and that's often enough. |
| **GCM** | CTR plus a built-in MAC (GMAC), in one operation | Nonce reuse here is worse: it leaks the authentication key, so the attacker can forge messages too. |

**AEAD** (authenticated encryption with associated data, for example AES-GCM) encrypts and authenticates in one call. The "associated data" is a header that stays readable but is covered by the tag. Use an AEAD whenever you need confidentiality. The general rule: **encryption without authentication is one flipped bit away from disaster**, because a ciphertext can be modified in ways that change the plaintext predictably.

Two things people get wrong in embedded projects:

- **Encrypted firmware is not signed firmware.** Encrypting an image keeps people from reading it. It does nothing to keep them from replacing it. These are two different jobs (Tool 5 does the second one).
- **Key size.** AES-128 is fine today. For a product that has to live 15 to 20 years, many people choose AES-256 where the hardware allows, because it costs almost nothing and gives a margin against future quantum computers (Tool 8).

**Words you'll hear:** symmetric encryption, AES, block cipher, mode of operation, ECB, CBC, CTR, GCM, IV, AEAD, ciphertext, plaintext.

## Tool 5: One creator, many checkers (signatures)

**The problem it solves:** firmware. A million cars have to verify that an update comes from the manufacturer, and *only the manufacturer* may be able to create one. With a MAC, everybody who can check can also forge, because the key is the same. Put the same MAC key into a million cars, and one of them will end up in a scrapyard, and from there in a lab.

**The picture:** the mailbox. Anyone can drop a letter through the slot, but only the owner has the key that opens the box. That's **asymmetric cryptography**: instead of one shared key, there's a **key pair**, a **public key** that can be given to everyone and a **private key** that never leaves its owner. What one does, only the other can undo or verify. (Look at the right half of the picture in Tool 4 again.)

Turned around, it's a **digital signature**. The manufacturer *signs* with the private key. Everybody *verifies* with the public key. You can make a seal only with the private stamp; anybody can check it with the public checker:

{% include crypto-fig.html fig="sigmac" caption="With a MAC, everybody who can check can also forge. With a signature, only the stamp holder can create, and everyone can check." %}

That asymmetry is the whole point. An ECU that holds only the public key can verify firmware but **cannot create it**. A key extracted from one ECU is a public key, which was never secret, so the attacker has gained nothing. (Compare with a MAC key extracted from one ECU: if the whole fleet shares it, that's a key to every car.)

### How it works

The signer hashes the image (Tool 1) and signs the *hash*. The verifier hashes the image they received, and checks the signature against it. If it's valid, two things are true: the data is unchanged, and it was signed by the holder of the matching private key.

<div class="mermaid">
flowchart LR
    subgraph Backend["Backend: holds the private key"]
        direction TB
        I["Firmware image"] --> H1["SHA-256"]
        H1 --> S["Sign with<br/>private key"]
        S --> SIG["Signature"]
    end
    subgraph ECU["ECU / HSM: holds only the public key"]
        direction TB
        I2["Received image"] --> H2["SHA-256"]
        H2 --> V{"Verify with<br/>public key"}
        SIG2["Received signature"] --> V
        V -->|valid| OK["Accept"]
        V -->|invalid| NO["Reject"]
    end
    I -. "image" .-> I2
    SIG -. "signature" .-> SIG2
</div>

This is also why firmware is signed and bus frames are not. A signature on every CAN frame would cost 64 bytes and several milliseconds, and the frame has 8 or 64 bytes to begin with. The typical split in a car is **asymmetric for the rare, important checks** (update, certificates) and **symmetric for the frequent, fast ones** (bus frames, boot checks). Asymmetric at update time, symmetric at boot time.

### The algorithms

| | RSA | ECC (ECDSA, EdDSA) |
|---|---|---|
| Security basis | Factoring large numbers | Discrete logarithm on an elliptic curve |
| Key size for roughly 128-bit security | 3072 bit | 256 bit (NIST P-256, Curve25519) |
| Signature size | 384 bytes at 3072 bit | 64 bytes |
| Typical pitfalls | Padding scheme (use PSS), key generation | Nonce handling in ECDSA, curve choice |

**ECDSA** has a famous trap: every signature needs a fresh, secret, random number (a nonce, again). Reuse it, or make it predictable, and the private key can be computed from two signatures. This has ended well-funded products before. Deterministic variants (RFC 6979) and **EdDSA** (Ed25519) take the random number out of the equation. Automotive HSMs typically speak ECDSA with P-256 first, so check what yours supports before designing around anything else.

Signing is a secret-key operation, so the signing key lives in a data-center HSM with a process around it. The ECU side only needs verification, which takes a few milliseconds. The signature operation itself doesn't depend on the image size, but hashing the image still takes its time.

**Words you'll hear:** public key, private key, key pair, digital signature, sign/verify, RSA, ECC, ECDSA, EdDSA, P-256, non-repudiation.

## Tool 6: Agreeing on a secret in public (Diffie-Hellman and KDFs)

**The problem it solves:** two parties who have never met want a shared symmetric key (for fast AES or CMAC), and the attacker hears everything they say. How do you agree on a secret in public? It sounds impossible. It isn't.

**The picture:** mixing paint. Fob and car publicly agree on a color, yellow. Each secretly picks their own color: the fob red, the car blue. Each mixes their secret into the yellow and sends the mixture across: orange and green. The attacker sees both mixtures. Then each adds their own secret to the *received* mixture: the fob adds red to green, the car adds blue to orange. Both end up with the same brown. The attacker can't make it: they'd need to unmix paint to get at a secret color, and unmixing is hard.

{% include crypto-fig.html fig="dh" caption="Diffie-Hellman with paint: both sides end up with the same colour, and the eavesdropper only ever sees colours it cannot unmix." %}

The real thing, **Diffie-Hellman** (in its elliptic-curve form, **ECDH**), replaces paint with a piece of mathematics where "unmixing" is just as hard. Two things to know:

- **Ephemeral keys** (a fresh pair per session) give **forward secrecy**: if a long-term key leaks tomorrow, yesterday's recorded sessions stay unreadable.
- Plain DH has one hole. The attacker can sit in the middle, do one DH with the fob and another with the car, and relay everything in between, reading it all. This is a **man-in-the-middle (MITM)** attack. To stop it, a real handshake like **TLS** also proves who's on the other end, with certificates and signatures (Tool 7).

### From one secret to many keys: the KDF

The result of DH is one shared secret, but you need several keys (one for encryption, one for MACs, maybe separate ones per direction). A **key derivation function (KDF)**, like HKDF, turns one secret plus some context into as many independent keys as you want. You'll meet it in two places:

- **Session keys:** a DH secret goes through a KDF to produce the actual encryption and MAC keys of a connection.
- **Key diversification:** a **master key** plus the ECU's serial number goes in, a **per-ECU key** comes out. The master stays in the backend, the ECU gets only its derived key, and an extracted ECU key tells the attacker nothing about the key of the next ECU. This is how "no secret is shared across the fleet" works in practice, and Part 2 comes back to it.

A **salt** is a non-secret value (unique or random) mixed into a KDF or a hash, so the same inputs don't produce the same outputs everywhere.

**Words you'll hear:** Diffie-Hellman, ECDH, ephemeral key, forward secrecy, man-in-the-middle, KDF, HKDF, key diversification, session key, salt.

## Tool 7: Whose key is this? (certificates)

**The problem it solves:** Tool 5 works only if the car holds the *real* public key of the manufacturer. What if the attacker hands the car their own public key and says "this is the manufacturer's"? Then their signatures verify perfectly. A public key on its own says nothing about who owns it.

**The picture:** a passport. It contains your name, your photo (the public key), and a stamp from an authority that the border officer already trusts. The officer doesn't know you, but knows the country's stamp is hard to fake.

A **certificate** (X.509) is exactly that: it binds a public key to an identity, and it's signed by a **certificate authority (CA)**. It carries the subject, the public key, a validity period, and extensions, which is where a design can put **roles** (what this tester is allowed to do).

Certificates form a **chain**: a root CA signs an intermediate CA, which signs the final ("leaf") certificate, for example one for a diagnostic tester. The ECU only needs to hold one thing: the **root CA public key**, called the **trust anchor**. From there, it can verify the whole chain. The whole set of CAs, certificates, rules and revocation is called a **PKI** (public key infrastructure).

The usual use in a car is to prove *who a tester is* before it's allowed to do dangerous things. It combines a certificate (who are you, what may you do) and a challenge-response (prove you hold the private key right now):

<div class="mermaid">
sequenceDiagram
    participant T as Tester
    participant E as ECU (HSM)
    T->>E: certificate chain
    E->>E: verify the chain up to the trust anchor, check validity and roles
    E->>T: challenge = fresh random value
    T->>E: signature over the challenge with the tester's private key
    E->>E: verify with the public key from the certificate
    Note over E: tester authenticated, rights come from the roles in the certificate
</div>

Verifying a certificate means checking every signature in the chain up to the trust anchor, the validity period, whether it was revoked, and what it's allowed to do. Two embedded problems hide in that list. First, **revocation** (CRLs, OCSP) assumes you can reach a server, and a parked ECU can't. Second, the **validity period** assumes you know today's date, and many ECUs have no trustworthy clock. Real designs work around this with short-lived certificates, counters or key updates instead of calendar dates.

**Words you'll hear:** certificate, X.509, CA, root CA, intermediate CA, chain, trust anchor, PKI, revocation, CRL, OCSP, role.

## Tool 8: The quantum footnote, and the exit plan

**The problem it solves:** the attacker is patient. A BCU built today lives 15 to 20 years. A large enough quantum computer would break RSA and ECC (Shor's algorithm), which means *every signature and every key agreement in this post*. Nobody knows when such a machine exists, but "within the lifetime of a car we ship today" is a planning assumption, not science fiction.

Symmetric crypto is much less affected. Grover's algorithm gives a quantum computer a quadratic speed-up on brute-force search, which is why 256-bit keys are the comfortable choice for long-lived products.

NIST has standardized replacements:

| Standard | Algorithm | Purpose | The embedded catch |
|---|---|---|---|
| FIPS 203 | ML-KEM | Key establishment | Larger messages than ECDH |
| FIPS 204 | ML-DSA | Signatures | ML-DSA-44: 1312-byte public key, 2420-byte signature (ECDSA P-256: 64 and 64), plus more RAM and code |
| FIPS 205 | SLH-DSA | Signatures, hash-based, stateless | Large signatures |
| SP 800-208 | LMS / XMSS | Signatures, hash-based, **stateful** | The signer must never reuse a one-time key, so the backend needs bulletproof state handling |

**Crypto agility** is the ability to replace an algorithm or a key in cars that are already on the road, without a redesign. It's cheap to plan for and very expensive to retrofit. The practical consequence: keep the part of the system that can never be updated (the first-stage bootloader) free of algorithm-specific code, and push the crypto into something that *can* be updated.

"**Harvest now, decrypt later**" is the attack that makes this urgent for confidentiality: record encrypted traffic today, read it when the computer exists. For signatures, the concern is different: forging something in the future, which is why long-lived roots of trust need a migration path.

**Words you'll hear:** post-quantum cryptography (PQC), Shor, Grover, ML-KEM, ML-DSA, LMS, stateful signature, crypto agility, harvest now decrypt later.

## The toolbox on one page

### CRC, hash, MAC, signature: who can fake it?

The same-looking "integrity field" can mean five very different things. This is the table I'd print:

| Mechanism | Needs a secret? | Catches random corruption? | Stops deliberate tampering? | Who can create it? | Typical use |
|---|---|---|---|---|---|
| Checksum (sum) | No | Some | No | Anyone | Legacy headers |
| **CRC** | No | Very well, for burst errors | **No**: it's linear, the attacker recomputes it or crafts a collision | Anyone | E2E, flash integrity, Ethernet FCS |
| **Hash** | No | Yes | **No**, unless the hash itself is protected | Anyone | Fingerprint, building block |
| **MAC** | Shared secret key | Yes | Yes, as long as the key stays secret | Everyone holding the key | Bus authentication, boot check, challenge-response |
| **Digital signature** | Private key (to sign), public key (to verify) | Yes | Yes | Only the holder of the private key | Firmware signing, certificates |

The consequence: **a CRC is a safety mechanism, a MAC or signature is a security mechanism**, and one cannot stand in for the other. A CRC developed to ASIL B (the second step on the automotive A-to-D scale of safety integrity levels) protects against random hardware faults. It protects against an attacker about as well as a spell-checker does. The other way round, a MAC computed by an HSM (a hardware security module, see [Part 2]({% post_url 2026-11-01-security-vocabulary-part-2-keys-hardware-and-the-ecu %})) and developed as QM (no safety requirements, ordinary quality management) catches the random bit flip too, but a safety case can't lean on it. So two checks over the same bytes for two different reasons: exactly what the boot concept in [Securing the Foundation, Part 1]({% post_url 2026-10-21-securing-the-foundation-part-1-threat-model-root-of-trust-and-boot %}) does for the application image.

### Which tool for which job?

| I need to... | Use | Why | Example |
|---|---|---|---|
| Detect random bit errors | CRC | Cheap, no key, good at burst errors | E2E, flash CRC |
| Fingerprint data | SHA-256 | No key, collision resistant | Block hash in an update manifest |
| Prove a message came from a key holder, and stop tampering | MAC: **CMAC** if you have AES hardware, **HMAC** if you only have a hash | Symmetric, fast, small | Bus authentication, boot MAC |
| Stop replay | Counter or challenge *inside* the MAC input | A MAC alone is replayable | Bus frames, immobilizer |
| Let many devices verify something only one party can create | Signature (ECDSA, EdDSA) | The verifier holds only the public key | Firmware signing |
| Keep data secret *and* unmodified | AEAD (AES-GCM) | One call for both | MACsec, TLS |
| Agree on a key over an open channel | ECDH plus authentication, then a KDF | No shared secret needed in advance | TLS, DoIP |
| Make many keys from one secret | KDF | Key separation and diversification | Per-ECU keys |
| Prove who a tester is | Certificate plus signature over a challenge | Rights from roles, no shared secret | Diagnostic authentication |
| Prove a party holds a shared key right now | Challenge-response with a TRNG challenge | Old answers are worthless | Immobilizer, debug unlock |

## Closing

Most of security vocabulary is three questions in different clothing: *who made this* (authenticity), *was it changed* (integrity), and *is it new* (freshness). Add "who can read it" (confidentiality) and "who can break it for everybody at once" (key management), and you've covered most of what the words in this post do. The attacker's moves in the story map one-to-one onto the tools, and no tool solves two of them. That's why real designs use five or six of them at once, and why "we added crypto" is never a complete sentence.

What this post didn't cover is everything around the crypto: where the keys live in an ECU, what the HSM is, how boot and update use all of this, what the bus and the diagnostic services look like, which attacks go around the crypto instead of through it, and what the process looks like. That's [Part 2]({% post_url 2026-11-01-security-vocabulary-part-2-keys-hardware-and-the-ecu %}).

## Sources and further reading

### Standards and specifications

- [NIST FIPS 197: Advanced Encryption Standard (AES)](https://csrc.nist.gov/pubs/fips/197/final)
- [NIST FIPS 180-4: Secure Hash Standard (SHA-1, SHA-2)](https://csrc.nist.gov/pubs/fips/180-4/final)
- [NIST FIPS 198-1: The Keyed-Hash Message Authentication Code (HMAC)](https://csrc.nist.gov/pubs/fips/198-1/final) and [RFC 2104: HMAC](https://www.rfc-editor.org/rfc/rfc2104)
- [NIST SP 800-38B: The CMAC Mode for Authentication](https://csrc.nist.gov/pubs/sp/800/38/b/upd1/final)
- [NIST SP 800-38D: Galois/Counter Mode (GCM) and GMAC](https://csrc.nist.gov/pubs/sp/800/38/d/final)
- [NIST FIPS 186-5: Digital Signature Standard](https://csrc.nist.gov/pubs/fips/186-5/final), [RFC 6979: Deterministic ECDSA](https://www.rfc-editor.org/rfc/rfc6979) and [RFC 8032: EdDSA](https://www.rfc-editor.org/rfc/rfc8032)
- [NIST SP 800-56A: Pair-wise key-establishment (DH, ECDH)](https://csrc.nist.gov/pubs/sp/800/56/a/r3/final)
- [RFC 5869: HKDF](https://www.rfc-editor.org/rfc/rfc5869) and [NIST SP 800-108: Key Derivation Using Pseudorandom Functions](https://csrc.nist.gov/pubs/sp/800/108/r1/final)
- [NIST SP 800-90A: Deterministic Random Bit Generators](https://csrc.nist.gov/pubs/sp/800/90/a/r1/final)
- [NIST FIPS 203 (ML-KEM)](https://csrc.nist.gov/pubs/fips/203/final), [FIPS 204 (ML-DSA)](https://csrc.nist.gov/pubs/fips/204/final), [FIPS 205 (SLH-DSA)](https://csrc.nist.gov/pubs/fips/205/final) and [SP 800-208 (LMS and XMSS)](https://csrc.nist.gov/pubs/sp/800/208/final)
- [RFC 5280: X.509 certificates and CRLs](https://www.rfc-editor.org/rfc/rfc5280) and [RFC 8446: TLS 1.3](https://www.rfc-editor.org/rfc/rfc8446)

### Books

- Christof Paar, Jan Pelzl: *Understanding Cryptography*, Springer, 2010. The friendliest way into AES, MACs, RSA and ECC for engineers.
- Niels Ferguson, Bruce Schneier, Tadayoshi Kohno: *Cryptography Engineering*, Wiley, 2010. How crypto fails in practice.
- Dan Boneh, Victor Shoup: [*A Graduate Course in Applied Cryptography*](https://toc.cryptobook.us/) (free online). When you want the proofs after all.
- Ross Anderson: *Security Engineering*, 3rd ed., Wiley, 2020
