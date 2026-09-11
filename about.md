---
layout: page
title: About
permalink: /about.html
---
Hi to everybody who stumbled over my blog. Highly welcome — you've found the corner of the internet where embedded software problems go to get roasted, mostly by the person who caused them.

I am an enthusiastic embedded SW architect writing about the problems I have faced during private and work-related projects, and the decisions that seemed reasonable at 5pm on a Friday.

<img src="{{ '/assets/images/embedded-reality-check.svg' | relative_url }}" alt="Meme: Expectation - a clean rocket labeled Clean Architecture shipping on Friday afternoon. Reality - a tangled wire ball and a bug, captioned it works on my debugger and GC decided the flashing sequence needed company." style="max-width: 100%; margin: 1.5em 0;">

*(Sponsored by nobody. Accuracy independently verified by every project I have ever shipped.)*

I had my first encounter with embedded SW during my mechatronics studies, where we had to develop a traffic light algorithm on an XC167 in assembler — a fantastic way to learn that "it compiles" and "it works" are two entirely different claims. Working part-time at a small company, I got the chance to design PCBs for various purposes, and learned the hard way that one small routing mistake can cost you weeks, a re-spin, and a fair bit of dignity. After that lesson landed, I focused more on the software side, which gave me the freedom to patch around minor hardware bugs instead of causing new ones — and to enjoy the particular flavor of freedom that comes from being able to fix your mistakes with a recompile instead of a new PCB order.

Little did I know I would get more and more hooked on embedded SW, eventually landing in the automotive industry, where "safety-critical" and "somebody already promised the customer a release date" coexist in ways that keep things interesting.

I want to share with everybody who is curious some insights about the problems I have faced and the reasoning behind decisions one might need to take — partly to help you avoid my mistakes, partly because writing them down is cheaper than therapy, and partly because I'm getting older and my memory isn't what it used to be :)

You can find some of the books I've read or am currently reading on the [Books](/books.html) page.

If you have questions, reach out to me via mail or [LinkedIn](https://www.linkedin.com/in/robert-koerner-8082a4214/) (I prefer the latter).

Topics I try to cover here include:

- **Security** — secure/authenticated boot and all the challenges that come with security
- **Flashing** — bootloaders and updateability
- **Communication** — from protocol to peripheral
- **RTOS and Partitioning** — memory layout, ASIL, task design, scheduling, real-world lessons from FreeRTOS/Zephyr and others
- **AUTOSAR** — practical concepts for developers coming from bare-metal or RTOS backgrounds
- **Firmware** — architecture patterns, portability, low-level design decisions
- **Debugging** — JTAG/SWD workflows, tracking down hard-to-reproduce bugs
- **AI** — where AI tooling actually helps in embedded/firmware engineering
- **Engineering Processes** — code review, branching, release practices for firmware teams

I will update or post as soon as I have some free time.
