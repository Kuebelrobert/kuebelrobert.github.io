---
layout: page
title: Books & Channels
permalink: /books.html
---
Some of the books I've read or am currently reading, and the YouTube channels I keep coming back to — mostly around embedded systems, software architecture, and engineering practice in general. Not an exhaustive list, and not all of it is technical; sometimes the best lessons for writing better firmware come from books that have nothing to do with firmware. Ratings are purely personal opinion, offered with the usual confidence of someone who has been wrong before and will be again.

Fair warning: I currently have two books open at once. This is either a sign of intellectual curiosity or of finishing things being hard — I'll let you decide.

## Currently reading

- **AI Engineering** — Chip Huyen — Detailed and dense content for AI nerds.
- **Hands-On Machine Learning with Scikit-Learn, Keras, and TensorFlow** — Aurélien Géron — My attempt at understanding the basics of machine learning. Not embedded-specific — this is training models on a desktop, not squeezing inference onto a Cortex-M — but useful groundwork before I try to figure out what actually survives the trip onto an MCU.

## Recommended Reads

- **Clean Architecture** — Robert C. Martin — Wanted to broaden my view beyond the embedded SW universe, and this book clearly delivers. It focuses on boundaries, dependencies, and principles in object-oriented design — turns out most "architecture decisions" still come down to "where do I put this one function."
- **Making Embedded Systems** — Elecia White — Started once before and picking it back up.
- **A Philosophy of Software Design, 2nd Edition** — John K. Ousterhout — The basics of SW architecture in a nutshell, and a good reminder of the principles you already know and violate anyway under deadline pressure.
- **Mastering Modern RTOS: Zephyr and ThreadX Internals, APIs, and Advanced Development** — Edward Row — Great for comparing two RTOS systems with completely different focuses. Prior exposure to FreeRTOS helps you benefit from it right from the start.
- **VIBE CODING: Build Production-Grade Software With GenAI, Chat, Agents and Beyond** — Gene Kim — Entertaining and motivating, but light on implementation and application details. If you're not on the AI train yet, this book will get you on it.
- **Artificial Intelligence: A Guide for Thinking Humans** — Melanie Mitchell — Digs into the early stages of machine learning and the predictions of what AI will be capable of. A good way to get to know AI's heritage and its founders — general AI background rather than anything that helps with firmware, but it's the kind of context that makes the embedded-AI hype easier to see through.
- **Security in Embedded Devices (Embedded Systems)** — Catherine H. Gebotys — Expensive, but worth every penny. Security will be one of the greatest challenges for SDVs.

<!-- Add new entries above, one per line, format: **Title** — Author — short comment. -->

## YouTube Channels

Books for depth, videos for the "aha" moment. These are the channels I keep coming back to, roughly grouped by what I watch them for.

### Embedded and low level

- **[Artful Bytes](https://www.youtube.com/@artfulbytes)** — Embedded systems from the ground up, including a long project series that builds a complete embedded system step by step.
- **[Low Level](https://www.youtube.com/@LowLevelTV)** — A vulnerability researcher on C, Rust, memory safety and security. Good for remembering why the pointer bug in your parser matters.
- **[Core Dumped](https://www.youtube.com/@CoreDumpped)** — Operating system concepts, animated: multitasking, threads, why software is OS-specific.
- **[Ryan Baker](https://www.youtube.com/@rybkr)** — Explainers that build up step by step what happens underneath: processes, CPU scheduling, file systems, the shell, build pipelines.
- **[Ben Eater](https://www.youtube.com/@BenEater)** — Computers built on breadboards, from logic gates to an 8-bit CPU and the 6502, plus networking. One of the clearest explanations of how a computer actually works.

### Building things

- **[bitluni](https://www.youtube.com/@bitluni)** — bitluni's lab: elaborate, funny gadget builds with microcontrollers, LEDs and a lot of creative misuse of peripherals.
- **[Stuff Made Here](https://www.youtube.com/@StuffMadeHere)** — Ambitious mechanical and electronic builds, with the failed iterations left in. A masterclass in engineering iteration.
- **[brenpoly](https://www.youtube.com/@brenpoly)** — Raspberry Pi builds with local AI agents and robotics. Fun proof of how far you get with small hardware and a local model.

### Understanding the concepts

- **[3Blue1Brown](https://www.youtube.com/@3blue1brown)** — Math, visualized: linear algebra, calculus and neural networks. Grant Sanderson also created Manim; its community edition renders the animations on this blog.
- **[MIT OpenCourseWare](https://www.youtube.com/@mitocw)** — Full MIT lecture courses for free, from computer architecture to algorithms and machine learning.
- **[Stanford Online](https://www.youtube.com/@stanfordonline)** — Stanford lectures and courses, strong on computer science and AI.

### Beyond the code

- **[Beyond Coding](https://www.youtube.com/@BeyondCoding)** — Conversations with CTOs, principal engineers and tech leads about the skills beyond writing code: communication, architecture decisions, careers.

<!-- Add new channels in the matching group, format: **[Name](https://www.youtube.com/@handle)** — short comment. -->
