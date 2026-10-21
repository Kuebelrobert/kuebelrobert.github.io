#!/usr/bin/env python3
"""
Animations for the "Securing the Foundation" series (embedded security for the BCU).

Reuses the palette and helpers of autosar_threadx_scenes.py, so all animations on
the blog look like one family. Text only (Pango), no LaTeX needed.

Render all scenes (720p30) into assets/videos/embedded-security/:
    python3 scripts/manim/render_all.py security

Or a single scene:
    manim -qm scripts/manim/security_scenes.py BootTimeline

Requires: manim (pip install manim; tested with manim 0.22 on Python 3.13).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from manim import *  # noqa: E402,F401
from autosar_threadx_scenes import (  # noqa: E402
    BG, INK, MUTED, GRID, OK, BAD, BLUE, AMBER, VIOLET, IDLE,
    txt, mono, box, token, header, footer, bar, lane, grow,
)


# ---------------------------------------------------------------- helpers ---
def say(scene, old, s, c=MUTED, fs=22):
    """Replace a status line in place (keeps its position)."""
    new = txt(s, fs, c).move_to(old)
    scene.play(Transform(old, new), run_time=0.3)


def status_line(scene, y=-2.3):
    """An invisible anchor for say(): an empty Text has no points, so no position."""
    t = txt(".", 22, BG).move_to([0, y, 0])
    scene.add(t)
    return t


def check(m, ok=True, fs=26):
    """A small ✓/✕ badge placed to the right of a mobject."""
    c = OK if ok else BAD
    d = Circle(radius=0.22, stroke_width=0, fill_color=c, fill_opacity=1)
    t = Text("✓" if ok else "✕", font_size=fs, color="#ffffff", font="Helvetica Neue", weight=BOLD).move_to(d)
    return VGroup(d, t).next_to(m, RIGHT, buff=0.15)


def flash_blocks(n=4, w=0.75, h=0.55, color=OK):
    g = VGroup(*[Rectangle(width=w, height=h, stroke_color=MUTED, stroke_width=2,
                           fill_color=color, fill_opacity=0.85) for _ in range(n)])
    return g.arrange(RIGHT, buff=0.06)


# ----------------------------------------------------------------- scenes ---
class HsmJobInterface(Scene):
    """Part 1, door 1: the application asks for a MAC, never gets the key."""

    def construct(self):
        header(self, "The HSM job interface",
               "The application gets results, never keys")
        footer(self, ["App core   job = { buffer, key slot 7 } -> HSM -> MAC   (the key itself never crosses the line)",
                      "Firewall   HSM flash/RAM are invisible to every application core, privileged or not"])

        core = box("Core 5 · QM", w=3.2, h=1.6, sub="diagnostics · immobilizer").move_to(LEFT * 4.5 + UP * 0.4)
        hsm = RoundedRectangle(width=4.6, height=3.4, corner_radius=0.14, stroke_color=VIOLET,
                               stroke_width=4).move_to(RIGHT * 3.7 + UP * 0.4)
        hl = txt("HSM", 26, VIOLET, True).next_to(hsm.get_top(), DOWN, buff=0.15)
        fw = DashedLine(hsm.get_corner(UL) + LEFT * 0.35, hsm.get_corner(DL) + LEFT * 0.35,
                        dash_length=0.12, stroke_color=BAD, stroke_width=5)
        fwl = txt("firewall", 18, BAD).next_to(fw, DOWN, buff=0.1)
        slots = VGroup(*[token(f"key slot {i}", c=VIOLET, fs=18) for i in (3, 7, 9)])
        slots.arrange(DOWN, buff=0.15).move_to(hsm.get_center() + DOWN * 0.25)
        self.play(*[FadeIn(m) for m in [core, hsm, hl, fw, fwl, slots]], run_time=0.7)

        status = status_line(self, -2.2)

        # 1: a normal job
        job = token("CMAC(buf, slot 7)", c=BLUE, fs=18).next_to(core, RIGHT, buff=0.2)
        self.play(FadeIn(job, scale=0.6), run_time=0.3)
        self.play(job.animate.next_to(slots[1], LEFT, buff=0.3), run_time=0.8)
        self.play(Indicate(slots[1], color=AMBER, scale_factor=1.12), FadeOut(job), run_time=0.6)
        mac = token("MAC", c=OK).move_to(slots[1].get_left() + LEFT * 1.3)
        self.play(FadeIn(mac, scale=0.6), run_time=0.2)
        self.play(mac.animate.next_to(core, DOWN, buff=0.25), run_time=0.8)
        say(self, status, "result out, key stays in", OK)
        self.wait(0.6)
        self.play(FadeOut(mac), run_time=0.2)

        # 2: the direct read of the key fails at the firewall
        say(self, status, "a compromised core tries to read the key directly ...", BAD)
        self.play(core[0].animate.set_stroke(BAD, 5), run_time=0.3)
        rd = token("read slot 7", c=BAD, fs=18).next_to(core, RIGHT, buff=0.2)
        self.play(FadeIn(rd, scale=0.6), run_time=0.2)
        self.play(rd.animate.move_to(fw.get_center() + LEFT * 0.75), run_time=0.7)
        cr = Cross(rd, stroke_color=BAD, stroke_width=6)
        self.play(Create(cr), run_time=0.3)
        say(self, status, "blocked by the firewall, not by the MPU", BAD)
        self.wait(0.6)
        self.play(FadeOut(rd), FadeOut(cr), run_time=0.3)

        # 3: while in, it can use the HSM ... after the fix, nothing left to take home
        say(self, status, "while it's in, it can still request MACs: bad, but limited", AMBER)
        for _ in range(2):
            j = token("CMAC", c=BAD, fs=16).next_to(core, RIGHT, buff=0.2)
            self.play(j.animate.move_to(slots[1].get_left() + LEFT * 1.3), run_time=0.45)
            self.play(FadeOut(j), run_time=0.15)
        upd = token("update: fix", c=OK, fs=18).next_to(core, UP, buff=0.25)
        self.play(FadeIn(upd, shift=DOWN * 0.3), run_time=0.4)
        self.play(core[0].animate.set_stroke(OK, 5), FadeOut(upd), run_time=0.5)
        self.play(Indicate(slots, color=OK, scale_factor=1.05), run_time=0.7)
        say(self, status, "after the fix: the attacker is out, and no key left with them", OK)
        self.wait(2.0)


class BootTimeline(Scene):
    """Part 1, door 2: strict secure boot misses the bus deadline, the mix doesn't."""

    def construct(self):
        header(self, "Secure boot vs. the 150 ms bus deadline",
               "HSM verifies ~10 MB at an assumed 40 MB/s (illustrative)")
        footer(self, ["Top     everything verified before start: ~255 ms, first bus answer too late",
                      "Bottom  Stage-1 strict (1.3 ms), apps run immediately, keys unlocked only after background verification"])

        x0, x1, tmax = -4.6, 5.8, 300.0

        def X(ms):
            return x0 + (x1 - x0) * ms / tmax

        # axis
        ax = Line([X(0), -2.35, 0], [X(300), -2.35, 0], stroke_color=GRID, stroke_width=2)
        ticks = VGroup(*[mono(f"{t} ms", 14).move_to([X(t), -2.6, 0]) for t in range(0, 301, 50)])
        dl = DashedLine([X(150), 2.55, 0], [X(150), -2.35, 0], stroke_color=BAD, stroke_width=3)
        dll = txt("bus deadline 150 ms", 18, BAD).next_to(dl, UP, buff=0.05)

        t1 = txt("strict secure boot", 22, INK, True).move_to([X(0), 2.15, 0], aligned_edge=LEFT)
        ya_h, ya_c = 1.6, 1.05
        la = VGroup(lane(ya_h, "HSM", x0=x0, x1=x1, fs=18), lane(ya_c, "cores", x0=x0, x1=x1, fs=18))

        t2 = txt("our mix: strict Stage-1, authenticated apps", 22, INK, True).move_to([X(0), 0.3, 0], aligned_edge=LEFT)
        yb_h, yb_c, yb_k = -0.25, -0.85, -1.45
        lb = VGroup(lane(yb_h, "HSM", x0=x0, x1=x1, fs=18), lane(yb_c, "cores", x0=x0, x1=x1, fs=18),
                    lane(yb_k, "keys", x0=x0, x1=x1, fs=18))
        self.play(*[FadeIn(m) for m in [ax, ticks, t1, la, t2, lb]], run_time=0.6)
        self.play(Create(dl), FadeIn(dll), run_time=0.4)

        # top: strict
        v = bar(X(0), X(255), ya_h, AMBER, 0.38, "verify everything (~10 MB)")
        self.play(grow(v), run_time=2.2, rate_func=linear)
        run = bar(X(255), X(300), ya_c, BLUE, 0.38, "run")
        self.play(grow(run), run_time=0.4)
        miss = txt("first bus answer at ~270 ms: missed", 18, BAD, True).next_to(run, LEFT, buff=0.2)
        self.play(FadeIn(miss), run_time=0.3)
        self.wait(0.6)

        # bottom: mix
        s1 = bar(X(0), X(3), yb_h, VIOLET, 0.38)
        s1l = txt("Stage-1 strict, 1.3 ms", 16, VIOLET).next_to(s1, UP, buff=0.05).align_to(s1, LEFT)
        self.play(grow(s1), FadeIn(s1l), run_time=0.4)
        vb = bar(X(3), X(258), yb_h, AMBER, 0.38, "verify apps in the background")
        cb = bar(X(3), X(300), yb_c, BLUE, 0.38, "apps run: init, CAN, lights")
        kb = bar(X(0), X(258), yb_k, IDLE, 0.38, "keys locked: no SecOC, no immobilizer, no 0x29")
        self.play(grow(vb), grow(cb), grow(kb), run_time=2.2, rate_func=linear)
        ku = bar(X(258), X(300), yb_k, OK, 0.38, "unlocked")
        self.play(grow(ku), run_time=0.4)
        ans = DashedLine([X(80), yb_c, 0], [X(80), -1.95, 0], stroke_color=OK, stroke_width=3)
        ansl = txt("first bus answer ~80 ms", 16, OK, True).next_to(ans, RIGHT, buff=0.1).align_to(ans, DOWN)
        self.play(Create(ans), FadeIn(ansl), run_time=0.4)
        self.wait(2.4)
