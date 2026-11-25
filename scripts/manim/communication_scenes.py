#!/usr/bin/env python3
"""
Animations for the posts on Automotive Ethernet and CAN FD.

Same style as autosar_threadx_scenes.py and security_scenes.py. Text only
(Pango), no LaTeX needed.

Render all scenes (720p30) into assets/videos/communication/:
    python3 scripts/manim/render_all.py communication

Or a single scene:
    manim -qm scripts/manim/communication_scenes.py CanArbitration

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
IDLE = "#b9b7b1"
DOM = "#2b2b2b"          # dominant bit fill

config.background_color = BG

FONT = "Helvetica Neue"


def txt(s, fs=24, c=INK, bold=False):
    return Text(s, font_size=fs, color=c, font=FONT, weight=BOLD if bold else NORMAL)


def mono(s, fs=18, c=MUTED):
    return Text(s, font_size=fs, color=c, font="Menlo")


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


# ----------------------------------------------------------------- scenes ---
class CanArbitration(Scene):
    """Bitwise arbitration on CAN: dominant 0 overwrites recessive 1, the lowest ID wins."""

    NODES = [("Node A", 0x123), ("Node B", 0x0F4), ("Node C", 0x0F2)]

    def construct(self):
        header(self, "CAN arbitration: the lowest ID wins",
               "Each node sends its identifier bit by bit and reads the bus back. Dominant 0 overwrites recessive 1.")
        footer(self, ["Bus     wired AND: if any node sends dominant (0), the bus is dominant · nothing is destroyed",
                      "CAN FD  arbitration at the nominal rate (e.g. 500 kbit/s), the faster data phase starts after it"])

        cw, x0 = 0.62, -3.5                                   # cell width, x of the first cell
        ys = [1.35, 0.6, -0.15]                               # node rows
        y_bus, y_wave = -0.95, -1.75
        cols = ["SOF"] + [f"ID{b}" for b in range(10, -1, -1)]

        def cx(i):
            return x0 + i * cw

        bits = [[0] + [(nid >> b) & 1 for b in range(10, -1, -1)] for _, nid in self.NODES]

        # static frame: row labels, column labels, empty cells
        labels = VGroup()
        for (name, nid), y in zip(self.NODES, ys):
            labels.add(txt(name, 22, INK, True).move_to([-5.6, y + 0.09, 0]),
                       mono(f"ID 0x{nid:03X}", 16).move_to([-5.6, y - 0.2, 0]))
        labels.add(txt("Bus", 22, INK, True).move_to([-5.6, y_bus, 0]))
        heads = VGroup(*[mono(c, 13).move_to([cx(i), ys[0] + 0.5, 0]) for i, c in enumerate(cols)])
        empty = VGroup(*[Square(cw - 0.08, stroke_color=GRID, stroke_width=2).move_to([cx(i), y, 0])
                         for y in ys + [y_bus] for i in range(len(cols))])
        hi, lo = y_wave + 0.25, y_wave - 0.25
        wl = VGroup(mono("recessive 1", 13).move_to([-5.6, hi, 0]), mono("dominant 0", 13).move_to([-5.6, lo, 0]))
        self.play(FadeIn(labels), FadeIn(heads), FadeIn(empty), FadeIn(wl), run_time=0.7)

        def cell(bit, y, i):
            sq = Square(cw - 0.08, stroke_color=MUTED, stroke_width=2,
                        fill_color=DOM if bit == 0 else BG, fill_opacity=1).move_to([cx(i), y, 0])
            t = txt(str(bit), 20, "#ffffff" if bit == 0 else INK, True).move_to(sq)
            return VGroup(sq, t)

        status = {}
        active = [True, True, True]
        cells = [[None] * len(cols) for _ in ys]
        level = 1                                             # bus idle = recessive
        xw = cx(0) - cw / 2
        wave = VGroup(Line([xw - 0.4, hi, 0], [xw, hi, 0], stroke_color=BLUE, stroke_width=4))
        self.add(wave)

        for i in range(len(cols)):
            col = Rectangle(width=cw, height=ys[0] - y_wave + 1.1, stroke_width=0, fill_color=AMBER,
                            fill_opacity=0.12).move_to([cx(i), (ys[0] + 0.5 + y_wave - 0.4) / 2, 0])
            sent = []
            for n in range(3):
                if active[n]:
                    cells[n][i] = cell(bits[n][i], ys[n], i)
                    sent.append(cells[n][i])
            self.play(FadeIn(col), *[FadeIn(c) for c in sent], run_time=0.3)

            bus = min(bits[n][i] for n in range(3) if active[n])
            bc = cell(bus, y_bus, i)
            y_new = hi if bus else lo
            seg = VGroup()
            if (1 if bus else 0) != level:
                seg.add(Line([xw, hi if level else lo, 0], [xw, y_new, 0], stroke_color=BLUE, stroke_width=4))
            seg.add(Line([xw, y_new, 0], [xw + cw, y_new, 0], stroke_color=BLUE, stroke_width=4))
            level, xw = bus, xw + cw
            self.play(FadeIn(bc), Create(seg), run_time=0.3)

            lost = [n for n in range(3) if active[n] and bits[n][i] == 1 and bus == 0]
            if lost:
                anims = []
                for n in lost:
                    active[n] = False
                    anims.append(cells[n][i][0].animate.set_stroke(BAD, 5))
                    status[n] = txt(f"sent 1, read 0 at {cols[i]}: lost,\nnow only listens", 17, BAD).move_to(
                        [cx(len(cols)) + 1.4, ys[n], 0])
                    anims.append(FadeIn(status[n]))
                    done = [c for c in cells[n][:i] if c is not None]
                    anims.append(VGroup(*done).animate.set_opacity(0.35))
                self.play(*anims, run_time=0.5)
                self.wait(0.4)
            self.play(FadeOut(col), run_time=0.15)

        win = [n for n in range(3) if active[n]][0]
        row = VGroup(*[c for c in cells[win] if c is not None])
        status[win] = txt("lowest ID: wins and keeps\nsending its frame", 17, OK, True).move_to(
            [cx(len(cols)) + 1.4, ys[win], 0])
        self.play(*[c[0].animate.set_stroke(OK, 4) for c in row], FadeIn(status[win]), run_time=0.5)
        note = txt("No collision, no time lost: A and B retry when the bus is idle again. The ID is the priority.",
                   20, MUTED).move_to([0, -2.45, 0])
        if note.width > 13.0:
            note.scale_to_fit_width(13.0)
        self.play(FadeIn(note), run_time=0.4)
        self.wait(2.5)


class SwitchLatency(Scene):
    """A small high-priority frame waits behind a full-size frame at every hop, unless frames can be preempted."""

    # Timing in microseconds at 100 Mbit/s: 1500-byte frame about 123 us on the wire,
    # 100-byte frame about 11 us, 5 us switch processing. The blue frame is ready at t = 5.
    BIG, SMALL, PROC, FRAG = 123, 11, 5, 5      # FRAG: wait for the next fragment boundary

    def construct(self):
        header(self, "Switched Ethernet: waiting behind big frames",
               "Blue: a 100-byte control frame over three 100 Mbit/s hops. Grey: a 1500-byte bulk frame already on the wire.")
        footer(self, ["Strict priority  a started frame can't be interrupted: up to one full-size frame of waiting per hop",
                      "Preemption      IEEE 802.1Qbu / 802.3br: the bulk frame is split, the control frame goes almost at once"])

        # path: sender, two switches, receiver
        names = ["Sender", "Switch 1", "Switch 2", "Receiver"]
        nodes = VGroup(*[RoundedRectangle(width=1.7, height=0.55, corner_radius=0.1, stroke_color=MUTED,
                                          stroke_width=2.5, fill_color=BG, fill_opacity=1) for _ in names])
        nodes.arrange(RIGHT, buff=1.35).move_to([0.6, 1.95, 0])
        for r, n in zip(nodes, names):
            r.add(txt(n, 18).move_to(r))
        links = VGroup(*[Line(nodes[i].get_right(), nodes[i + 1].get_left(), stroke_color=GRID, stroke_width=4)
                         for i in range(3)])
        link_l = VGroup(*[mono(f"link {i + 1}", 13).next_to(links[i], UP, buff=0.06) for i in range(3)])

        x0, scale = -4.5, 9.4 / 420               # x of t = 0, units per microsecond

        def X(t):
            return x0 + t * scale

        ya = [1.0, 0.6, 0.2]
        yb = [-0.75, -1.15, -1.55]
        ta = txt("Strict priority", 20, INK, True).move_to([X(0), 1.38, 0], aligned_edge=LEFT)
        tb = txt("Frame preemption", 20, INK, True).move_to([X(0), -0.37, 0], aligned_edge=LEFT)
        lanes = VGroup()
        for ys in (ya, yb):
            for i, y in enumerate(ys):
                lanes.add(Line([X(0), y, 0], [X(420), y, 0], stroke_color=GRID, stroke_width=1.5),
                          mono(f"link {i + 1}", 13).move_to([X(0) - 0.7, y, 0]))
        grid = VGroup()
        for t in range(0, 401, 100):
            grid.add(DashedLine([X(t), ya[0] + 0.2, 0], [X(t), yb[-1] - 0.2, 0], stroke_color=GRID,
                                stroke_width=1, dash_length=0.06),
                     mono(f"{t} µs", 12).move_to([X(t), yb[-1] - 0.38, 0]))
        self.play(FadeIn(nodes), FadeIn(links), FadeIn(link_l), FadeIn(ta), FadeIn(tb), FadeIn(lanes),
                  FadeIn(grid), run_time=0.7)

        def frame(t0, t1, y, color, label=None):
            r = Rectangle(width=max((t1 - t0) * scale, 0.02), height=0.26, stroke_width=0, fill_color=color,
                          fill_opacity=1).move_to([X((t0 + t1) / 2), y, 0])
            if label:
                return VGroup(r, txt(label, 13, "#ffffff", True).move_to(r))
            return VGroup(r)

        def hop_on(i):
            return links[i].animate.set_stroke(BLUE, 6)

        def hop_off(i):
            return links[i].animate.set_stroke(GRID, 4)

        # strict priority: blue waits until the grey frame on the port is done
        ready, ends = 5, []
        for i, y in enumerate(ya):
            g0 = ready - 2
            grey = frame(g0, g0 + self.BIG, y, IDLE, "1500 B bulk")
            start = g0 + self.BIG
            blue = frame(start, start + self.SMALL, y, BLUE)
            wait = DashedLine([X(ready), y + 0.2, 0], [X(start), y + 0.2, 0], stroke_color=BAD, stroke_width=2,
                              dash_length=0.05)
            self.play(hop_on(i), GrowFromEdge(grey, LEFT), run_time=0.45)
            self.play(Create(wait), run_time=0.35)
            self.play(GrowFromEdge(blue, LEFT), hop_off(i), run_time=0.3)
            ready = start + self.SMALL + self.PROC
            ends.append(start + self.SMALL)
        total_a = ends[-1] - 5
        la = txt(f"≈ {total_a / 1000:.1f} ms", 22, BAD, True).move_to([X(420) + 0.9, ya[1], 0])
        self.play(FadeIn(la), run_time=0.3)

        # preemption: grey is split at the next fragment boundary, blue goes, grey resumes
        ready, ends = 5, []
        for i, y in enumerate(yb):
            g0 = ready - 2
            cut = ready + self.FRAG
            g1 = frame(g0, cut, y, IDLE)
            blue = frame(cut, cut + self.SMALL, y, BLUE)
            g2 = frame(cut + self.SMALL, g0 + self.BIG + self.SMALL, y, IDLE, "rest of the bulk frame")
            self.play(hop_on(i), GrowFromEdge(g1, LEFT), run_time=0.3)
            self.play(GrowFromEdge(blue, LEFT), run_time=0.3)
            self.play(GrowFromEdge(g2, LEFT), hop_off(i), run_time=0.35)
            ready = cut + self.SMALL + self.PROC
            ends.append(cut + self.SMALL)
        total_b = ends[-1] - 5
        lb = txt(f"≈ {total_b / 1000:.2f} ms", 22, OK, True).move_to([X(420) + 0.9, yb[1], 0])
        self.play(FadeIn(lb), run_time=0.3)

        note = txt("Throughput is the same in both cases. Only the worst-case latency of the control frame changes.",
                   18, MUTED).move_to([0, -2.35, 0])
        if note.width > 13.0:
            note.scale_to_fit_width(13.0)
        self.play(FadeIn(note), run_time=0.4)
        self.wait(2.5)


class FrameOverhead(Scene):
    """A 16-byte SOME/IP event, wrapped layer by layer until it is 102 bytes on the wire; then bundling."""

    # (name, bytes, color, filled) in wire order; built up from the payload outwards
    LAYOUT = [("Preamble + SFD", 8, IDLE, False), ("Ethernet", 14, "#8a8780", True), ("VLAN", 4, "#a8a59e", True),
              ("IPv4", 20, "#3a8f8f", True), ("UDP", 8, "#7a5cc4", True), ("SOME/IP", 16, AMBER, True),
              ("data", 16, BLUE, True), ("FCS", 4, "#8a8780", True), ("Gap", 12, IDLE, False)]
    ORDER = ["data", "SOME/IP", "UDP", "IPv4", "VLAN", "Ethernet", "FCS", "Preamble + SFD", "Gap"]

    def construct(self):
        header(self, "16 bytes of data, 102 bytes on the wire",
               "A small SOME/IP event, wrapped by every layer on its way to the cable.")
        footer(self, ["Frame    82 B from Ethernet header to FCS, above the 64 B minimum, so no padding",
                      "Wire     plus 8 B preamble and 12 B inter-frame gap: 102 B = about 8 µs per event at 100 Mbit/s"])

        total = sum(b for _, b, _, _ in self.LAYOUT)
        unit = 12.4 / total
        x, y = -6.2, 1.0
        blocks, labels = {}, {}
        for k, (name, n, color, filled) in enumerate(self.LAYOUT):
            w = n * unit
            if filled:
                r = Rectangle(width=w, height=0.62, stroke_color=BG, stroke_width=1.5, fill_color=color,
                              fill_opacity=1)
            else:
                r = DashedVMobject(Rectangle(width=w, height=0.62, stroke_color=MUTED, stroke_width=2),
                                   num_dashes=int(n * 2.2))
            r.move_to([x + w / 2, y, 0])
            up = k % 2 == 0
            lbl = VGroup(txt(name, 15, INK, True), mono(f"{n} B", 13)).arrange(DOWN, buff=0.03)
            lbl.next_to(r, UP if up else DOWN, buff=0.12)
            tick = Line(r.get_top() if up else r.get_bottom(), lbl.get_bottom() if up else lbl.get_top(),
                        stroke_color=GRID, stroke_width=1.5)
            blocks[name], labels[name] = r, VGroup(lbl, tick)
            x += w

        def counter(n):
            return VGroup(txt(f"{n} B on the wire", 24, INK, True),
                          txt(f"data share {round(16 * 100 / n)} %", 20, BLUE if n == 16 else MUTED)).arrange(
                RIGHT, buff=0.5).move_to([0, -0.45, 0])

        size = 0
        cnt = None
        for name in self.ORDER:
            size += next(b for nm, b, _, _ in self.LAYOUT if nm == name)
            new = counter(size)
            anims = [FadeIn(blocks[name], scale=1.15), FadeIn(labels[name])]
            anims.append(FadeIn(new) if cnt is None else Transform(cnt, new))
            self.play(*anims, run_time=0.55)
            if cnt is None:
                cnt = new
            self.wait(0.2)
        self.wait(0.8)

        # bundling: four events in four frames vs four events in one frame
        per_frame = total                                     # 102 B each
        bundled = total - 32 + 4 * 32                         # one set of headers, four SOME/IP messages
        t = txt("Four events of 16 B:", 20, INK, True).move_to([-6.2, -1.25, 0], aligned_edge=LEFT)
        bu = 12.4 / (4 * per_frame)
        sep = VGroup()
        for i in range(4):
            sep.add(Rectangle(width=per_frame * bu - 0.04, height=0.3, stroke_width=0, fill_color=IDLE,
                              fill_opacity=1).move_to([-6.2 + (i + 0.5) * per_frame * bu, -1.7, 0]))
        sep_l = txt(f"4 frames: {4 * per_frame} B, data share {round(64 * 100 / (4 * per_frame))} %", 17, BAD).next_to(
            sep, DOWN, buff=0.08).align_to(sep, LEFT)
        one = Rectangle(width=bundled * bu, height=0.3, stroke_width=0, fill_color=OK, fill_opacity=1)
        one.move_to([-6.2 + bundled * bu / 2, -2.3, 0])
        one_l = txt(f"1 bundled frame: {bundled} B, data share {round(64 * 100 / bundled)} %", 17, OK).next_to(
            one, RIGHT, buff=0.25)
        self.play(FadeIn(t), run_time=0.3)
        self.play(LaggedStart(*[GrowFromEdge(r, LEFT) for r in sep], lag_ratio=0.25), FadeIn(sep_l),
                  run_time=1.0)
        hint = mono("bundled: Ethernet, IP and UDP headers once, still one SOME/IP header per event", 14).next_to(
            one, DOWN, buff=0.1).align_to(one, LEFT)
        self.play(GrowFromEdge(one, LEFT), FadeIn(one_l), FadeIn(hint), run_time=0.6)
        self.wait(2.5)
