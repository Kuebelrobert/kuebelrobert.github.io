#!/usr/bin/env python3
"""
Animations for the post "Running an AUTOSAR Project on ThreadX".

Each scene illustrates one AUTOSAR mechanism and names its ThreadX mapping in the
footer. Text only (Pango), no LaTeX needed.

Render all scenes (720p30) into assets/videos/autosar-threadx/:
    python3 scripts/manim/render_all.py

Or a single scene:
    manim -qm scripts/manim/autosar_threadx_scenes.py EventsToThreads

Requires: manim (pip install manim; tested with manim 0.22 on Python 3.13).
"""
from manim import *

# Palette shared with the blog's other figures (status colors + categorical blue).
BG = "#fdfdfd"
INK = "#111111"
MUTED = "#52514e"
GRID = "#c9c7c1"
OK = "#0ca30c"
BAD = "#d03b3b"
BLUE = "#2a78d6"
AMBER = "#e09a00"
VIOLET = "#4a3aa7"
IDLE = "#b9b7b1"

config.background_color = BG


# ---------------------------------------------------------------- helpers ---
FONT = "Helvetica Neue"


def txt(s, fs=24, c=INK, bold=False):
    return Text(s, font_size=fs, color=c, font=FONT, weight=BOLD if bold else NORMAL)


def mono(s, fs=18, c=MUTED):
    return Text(s, font_size=fs, color=c, font="Menlo")


def box(label, w=3.2, h=1.0, stroke=MUTED, sub=None, fs=24):
    r = RoundedRectangle(width=w, height=h, corner_radius=0.12, stroke_color=stroke,
                         stroke_width=3, fill_color=BG, fill_opacity=1)
    if sub:
        g = VGroup(txt(label, fs), txt(sub, fs - 6, MUTED)).arrange(DOWN, buff=0.08)
    else:
        g = txt(label, fs)
    g.move_to(r)
    return VGroup(r, g)


def token(s, c=BLUE, fs=22):
    t = Text(s, font_size=fs, color="#ffffff", font=FONT, weight=BOLD)
    r = RoundedRectangle(width=max(0.75, t.width + 0.35), height=0.5, corner_radius=0.12,
                         stroke_width=0, fill_color=c, fill_opacity=1)
    t.move_to(r)
    return VGroup(r, t)


def header(scene, title, sub):
    t = txt(title, 32, INK, True).to_corner(UL, buff=0.45)
    s = txt(sub, 20, MUTED).next_to(t, DOWN, buff=0.12, aligned_edge=LEFT)
    scene.add(t, s)
    return VGroup(t, s)


def footer(scene, lines):
    g = VGroup(*[mono(l) for l in lines]).arrange(DOWN, aligned_edge=LEFT, buff=0.1)
    if g.width > 13.2:
        g.scale_to_fit_width(13.2)
    g.to_corner(DL, buff=0.4)
    scene.add(g)
    return g


def bar(x0, x1, y, color, h=0.42, label=None, fs=18):
    r = Rectangle(width=max(x1 - x0, 0.01), height=h, stroke_width=0,
                  fill_color=color, fill_opacity=1).move_to([(x0 + x1) / 2, y, 0])
    if label:
        t = txt(label, fs, "#ffffff", True).move_to(r)
        if t.width > r.width - 0.1:
            t.scale_to_fit_width(r.width - 0.1)
        return VGroup(r, t)
    return VGroup(r)


def lane(y, name, x0=-5.0, x1=5.6, fs=20):
    line = Line([x0, y, 0], [x1, y, 0], stroke_color=GRID, stroke_width=2)
    lbl = txt(name, fs, MUTED).next_to(line, LEFT, buff=0.25)
    return VGroup(line, lbl)


def grow(b):
    return GrowFromEdge(b, LEFT)


# ----------------------------------------------------------------- scenes ---
class EventsToThreads(Scene):
    """RTE events activate runnables; on ThreadX they become event flags of a thread."""

    def construct(self):
        header(self, "RTE events  ->  ThreadX threads",
               "Every RTE event sets a flag; the thread wakes up and runs the runnables mapped to the flags")
        footer(self, ["AUTOSAR  TimingEvent · DataReceivedEvent · OperationInvokedEvent ... activate runnables in OS tasks",
                      "ThreadX  tx_timer / shim -> tx_event_flags_set() · thread: tx_event_flags_get(TX_OR_CLEAR) -> dispatch"])
        src = VGroup(
            box("TimingEvent 10 ms", w=3.6, h=0.75, fs=20, sub=None),
            box("DataReceivedEvent", w=3.6, h=0.75, fs=20),
            box("OperationInvokedEvent", w=3.6, h=0.75, fs=20),
        ).arrange(DOWN, buff=0.35).move_to(LEFT * 4.5 + UP * 0.35)
        bits = VGroup(*[Square(side_length=0.7, stroke_color=MUTED, stroke_width=3, fill_color=BG, fill_opacity=1)
                        for _ in range(3)]).arrange(DOWN, buff=0.4).move_to(LEFT * 0.6 + UP * 0.35)
        bit_l = VGroup(*[txt(f"bit {i}", 18, MUTED).next_to(bits[i], LEFT, buff=0.12) for i in range(3)])
        fl = txt("event flags", 20, MUTED).next_to(bits, UP, buff=0.18)
        thr = RoundedRectangle(width=4.4, height=3.1, corner_radius=0.12, stroke_color=MUTED, stroke_width=3)
        thr.move_to(RIGHT * 3.9 + UP * 0.35)
        tl = txt("Task_10ms thread", 22, INK, True).next_to(thr.get_top(), DOWN, buff=0.15)
        runs = VGroup(*[box(n, w=3.8, h=0.55, fs=18) for n in
                        ["R_Control  (bit 0)", "R_OnSpeed  (bit 1)", "R_ServeOp  (bit 2)"]])
        runs.arrange(DOWN, buff=0.15).next_to(tl, DOWN, buff=0.2)
        arrows = VGroup(*[Arrow(src[i].get_right(), bit_l[i].get_left(), buff=0.12, color=GRID,
                                stroke_width=3) for i in range(3)])
        self.play(*[FadeIn(m) for m in [src, bits, bit_l, fl, thr, tl, runs, arrows]], run_time=0.7)

        def fire(idx_list):
            self.play(*[src[i][0].animate.set_stroke(AMBER, 5) for i in idx_list], run_time=0.25)
            self.play(*[bits[i].animate.set_fill(AMBER, 1) for i in idx_list],
                      *[src[i][0].animate.set_stroke(MUTED, 3) for i in idx_list], run_time=0.35)
            self.play(thr.animate.set_stroke(OK, 5), run_time=0.25)
            for i in idx_list:
                self.play(runs[i][0].animate.set_fill(OK, 0.25).set_stroke(OK, 4), run_time=0.35)
                self.play(runs[i][0].animate.set_fill(BG, 1).set_stroke(MUTED, 3),
                          bits[i].animate.set_fill(BG, 1), run_time=0.3)
            self.play(thr.animate.set_stroke(MUTED, 3), run_time=0.2)

        fire([0])
        fire([1])
        fire([0, 2])
        note = txt("two flags at once: one wake-up, runnables in configured order", 22, MUTED).move_to(DOWN * 2.0)
        self.play(FadeIn(note), run_time=0.3)
        self.wait(1.8)


class ResourceVsMutex(Scene):
    """OSEK resource (immediate priority ceiling) vs. mutex with priority inheritance."""

    def construct(self):
        header(self, "OS resource (priority ceiling) vs. mutex (priority inheritance)",
               "Low-priority L holds the lock. M and H become ready while it does.")
        footer(self, ["AUTOSAR  GetResource()/ReleaseResource(): L runs at the ceiling for the whole critical section",
                      "ThreadX  ceiling: tx_thread_preemption_change() · inheritance: tx_mutex_create(..., TX_INHERIT)"])
        t1 = txt("resource = priority ceiling  (ThreadX: preemption-threshold)", 22, INK, True).move_to([0, 1.9, 0])
        t2 = txt("mutex + priority inheritance  (ThreadX: TX_INHERIT)", 22, INK, True).move_to([0, -0.28, 0])
        ya = {"H": 1.3, "M": 0.9, "L": 0.5}
        yb = {"H": -0.9, "M": -1.3, "L": -1.7}
        la = VGroup(*[lane(y, k) for k, y in ya.items()])
        lb = VGroup(*[lane(y, k) for k, y in yb.items()])
        self.play(FadeIn(t1), FadeIn(t2), FadeIn(la), FadeIn(lb), run_time=0.6)

        def ready(x, y):
            return Triangle(color=INK, fill_color=INK, fill_opacity=1).scale(0.08).rotate(PI).move_to([x, y + 0.24, 0])

        h = 0.3
        # ceiling
        seq_a = [
            (bar(-5.0, -4.2, ya["L"], BLUE, h), None),
            (bar(-4.2, -0.8, ya["L"], AMBER, h, "L holds resource"), [ready(-3.4, ya["M"]), ready(-2.4, ya["H"])]),
            (bar(-0.8, 1.4, ya["H"], OK, h, "H"), None),
            (bar(1.4, 3.0, ya["M"], VIOLET, h, "M"), None),
            (bar(3.0, 4.2, ya["L"], BLUE, h), None),
        ]
        # inheritance
        seq_b = [
            (bar(-5.0, -4.2, yb["L"], BLUE, h), None),
            (bar(-4.2, -3.4, yb["L"], AMBER, h, "L locked"), [ready(-3.4, yb["M"])]),
            (bar(-3.4, -2.4, yb["M"], VIOLET, h, "M"), [ready(-2.4, yb["H"])]),
            (bar(-2.4, -2.0, yb["H"], OK, h), None),
            (bar(-2.0, -0.4, yb["L"], AMBER, h, "L boosted"), None),
            (bar(-0.4, 1.8, yb["H"], OK, h, "H"), None),
            (bar(1.8, 2.6, yb["M"], VIOLET, h, "M"), None),
            (bar(2.6, 3.8, yb["L"], BLUE, h), None),
        ]
        for (ba, ma), (bb, mb) in zip(seq_a + [(None, None)] * (len(seq_b) - len(seq_a)), seq_b):
            anims = []
            if ba is not None:
                anims.append(grow(ba))
                if ma:
                    anims += [FadeIn(m) for m in ma]
            anims.append(grow(bb))
            if mb:
                anims += [FadeIn(m) for m in mb]
            self.play(*anims, run_time=0.55)
        blk = txt("blocked", 16, BAD, True).move_to([-1.2, yb["H"], 0])
        self.play(FadeIn(blk), run_time=0.3)
        na = txt("M never runs inside L's critical section · no deadlock by design", 20, OK).move_to([0.3, 0.05, 0])
        nb = txt("M ran while L held the lock · nested mutexes can deadlock", 20, BAD).move_to([0.3, -2.15, 0])
        self.play(FadeIn(na), FadeIn(nb), run_time=0.4)
        self.wait(2.2)


class IocCrossCore(Scene):
    """Cross-core transfer: AUTOSAR IOC vs. a hand-made seqlock mailbox between two ThreadX instances."""

    def construct(self):
        header(self, "Cross-core communication: IOC vs. hand-made mailbox",
               "Two cores, two ThreadX instances, no shared kernel. The bridge is shared memory and a protocol.")
        footer(self, ["AUTOSAR  IocWrite()/IocRead() (unqueued) · IocSend()/IocReceive() (queued), generated by the OS",
                      "ThreadX  seqlock mailbox, non-cacheable · queued: ring buffer + inter-core IRQ -> tx_semaphore_put()"])
        c1 = box("Core 1 · QM", w=3.4, h=2.4, sub="ThreadX instance B\nwriter").move_to(RIGHT * 4.6 + UP * 0.3)
        c0 = box("Core 0 · ASIL B", w=3.4, h=2.4, sub="ThreadX instance A\nreader").move_to(LEFT * 4.6 + UP * 0.3)
        mem = RoundedRectangle(width=3.6, height=2.4, corner_radius=0.12, stroke_color=MUTED, stroke_width=3).move_to(UP * 0.3)
        ml = txt("shared SRAM · non-cacheable", 18, MUTED).next_to(mem, UP, buff=0.12)
        seq_l = mono("seq", 24, INK).move_to(mem.get_center() + LEFT * 1.0 + UP * 0.5)
        dat_l = mono("data", 24, INK).move_to(mem.get_center() + LEFT * 1.0 + DOWN * 0.4)
        seq_v = token("4", c=OK).move_to(mem.get_center() + RIGHT * 0.7 + UP * 0.5)
        dat_v = token("v1").move_to(mem.get_center() + RIGHT * 0.7 + DOWN * 0.4)
        self.play(*[FadeIn(m) for m in [c0, c1, mem, ml, seq_l, dat_l, seq_v, dat_v]], run_time=0.7)

        def set_tok(old, label, color):
            n = token(label, c=color).move_to(old)
            self.play(Transform(old, n), run_time=0.35)

        wl = txt("", 20, MUTED).move_to(RIGHT * 4.6 + DOWN * 1.5)
        rl = txt("", 20, MUTED).move_to(LEFT * 4.6 + DOWN * 1.5)

        def say(old, s, c, pos):
            n = txt(s, 20, c).move_to(pos)
            self.play(Transform(old, n), run_time=0.25)

        # clean write, clean read
        say(wl, "seq++ (odd: writing)", AMBER, RIGHT * 4.6 + DOWN * 1.5)
        set_tok(seq_v, "5", AMBER)
        set_tok(dat_v, "v2", BLUE)
        say(wl, "seq++ (even: done)", OK, RIGHT * 4.6 + DOWN * 1.5)
        set_tok(seq_v, "6", OK)
        say(rl, "s1=6 · copy · s2=6", OK, LEFT * 4.6 + DOWN * 1.5)
        cp = dat_v.copy()
        self.play(cp.animate.move_to(c0.get_right() + LEFT * 0.7 + DOWN * 0.7), run_time=0.5)
        say(rl, "consistent -> E2E check", OK, LEFT * 4.6 + DOWN * 1.5)
        self.wait(0.5)

        # torn read, retry
        say(wl, "seq++ (odd: writing)", AMBER, RIGHT * 4.6 + DOWN * 1.5)
        set_tok(seq_v, "7", AMBER)
        say(rl, "try 1: s1=7 odd -> retry", AMBER, LEFT * 4.6 + DOWN * 1.5)
        set_tok(dat_v, "v3", BLUE)
        say(wl, "seq++ (even: done)", OK, RIGHT * 4.6 + DOWN * 1.5)
        set_tok(seq_v, "8", OK)
        say(rl, "try 2: s1=8 · copy · s2=8 ok", OK, LEFT * 4.6 + DOWN * 1.5)
        cp2 = dat_v.copy()
        self.play(FadeOut(cp), cp2.animate.move_to(c0.get_right() + LEFT * 0.7 + DOWN * 0.7), run_time=0.5)
        rule = txt("max 3 tries, then 'stale': a QM writer must never stall the ASIL reader", 22, BAD).move_to(DOWN * 2.0)
        self.play(FadeIn(rule), run_time=0.3)
        self.wait(2.0)
