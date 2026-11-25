#!/usr/bin/env python3
"""
Animations for the series "Automotive Ethernet for the SDV".

Addresses, frame sizes and timings come from the virtual vehicle network used in
the post (gateway .1, camera .2, brake .3, tester .100).

Render all scenes (720p30) into assets/videos/automotive-ethernet/:
    python3 scripts/manim/render_all.py ethernet

Requires: manim (pip install manim; tested with manim 0.22 on Python 3.13).
"""
from manim import *

# Palette shared with the blog's other figures.
BG = "#fdfdfd"
INK = "#111111"
MUTED = "#52514e"
GRID = "#c9c7c1"
OK = "#0ca30c"
BAD = "#d03b3b"
BLUE = "#2a78d6"
AMBER = "#e09a00"
IDLE = "#b9b7b1"
TEAL = "#3a8f8f"
PURPLE = "#7a5cc4"
GREY1 = "#8a8780"

config.background_color = BG
FONT = "Helvetica Neue"


def txt(s, fs=24, c=INK, bold=False):
    return Text(s, font_size=fs, color=c, font=FONT, weight=BOLD if bold else NORMAL)


def mono(s, fs=18, c=MUTED):
    return Text(s, font_size=fs, color=c, font="Menlo")


def fit(m, w):
    if m.width > w:
        m.scale_to_fit_width(w)
    return m


def header(scene, title, sub):
    t = txt(title, 32, INK, True).to_corner(UL, buff=0.45)
    s = fit(txt(sub, 20, MUTED), 13.2).next_to(t, DOWN, buff=0.12, aligned_edge=LEFT)
    scene.add(t, s)


def footer(scene, lines):
    g = fit(VGroup(*[mono(l) for l in lines]).arrange(DOWN, aligned_edge=LEFT, buff=0.1), 13.2)
    g.to_corner(DL, buff=0.4)
    scene.add(g)


def box(pos, name, sub=None, w=2.0, h=0.8, c=MUTED, fs=20, fill=BG):
    r = RoundedRectangle(width=w, height=h, corner_radius=0.1, stroke_color=c, stroke_width=2.5,
                         fill_color=fill, fill_opacity=1)
    t = VGroup(txt(name, fs, INK, True))
    if sub:
        t.add(mono(sub, 13))
    t.arrange(DOWN, buff=0.06)
    fit(t, w - 0.15)
    g = VGroup(r, t.move_to(r)).move_to(pos)
    return g


def pkt(label, c=BLUE, w=None):
    t = txt(label, 15, "#ffffff", True)
    r = RoundedRectangle(width=w or t.width + 0.25, height=0.34, corner_radius=0.07, stroke_width=0,
                         fill_color=c, fill_opacity=1)
    return VGroup(r, t.move_to(r))


def note(s, y, c=MUTED, fs=20, w=13.0):
    return fit(txt(s, fs, c), w).move_to([0, y, 0])


# ----------------------------------------------------------------- scenes ---
class SdvArchitectures(Scene):
    """The same twelve functions, hosted in four E/E architectures."""

    COL = {"B": BLUE, "P": TEAL, "A": AMBER, "I": PURPLE}

    def construct(self):
        header(self, "Where the software lives: four E/E architectures",
               "Twelve functions stay the same. What changes is the box that hosts them and the network between the boxes.")
        car = RoundedRectangle(width=8.2, height=4.5, corner_radius=1.1, stroke_color=GRID, stroke_width=4).move_to(
            [-2.6, -0.2, 0])
        self.add(car, mono("front", 13).move_to([-6.95, -0.2, 0]).rotate(PI / 2))
        leg = VGroup()
        for k, n in [("B", "body"), ("P", "powertrain, chassis"), ("A", "ADAS"), ("I", "infotainment")]:
            leg.add(VGroup(Dot(radius=0.11, color=self.COL[k]), txt(n, 16, MUTED)).arrange(RIGHT, buff=0.12))
        leg.arrange(RIGHT, buff=0.45).move_to([-2.6, -2.85, 0])
        self.add(leg)

        def place(x, y):
            return np.array([x - 2.6, y - 0.2, 0])

        def bx(x, y, n, w=1.5, h=0.75, c=MUTED):
            r = RoundedRectangle(width=w, height=h, corner_radius=0.08, stroke_color=c, stroke_width=2.5,
                                 fill_color=BG, fill_opacity=1).move_to(place(x, y))
            t = fit(txt(n, 14, INK, True), w - 0.12).move_to(r.get_top() + DOWN * 0.17)
            return VGroup(r, t)

        def ln(a, b, dashed=False, c=INK):
            L = (DashedLine if dashed else Line)(place(*a), place(*b), stroke_color=c, stroke_width=4)
            return L

        def row(cx, cy, n, dx=0.3):
            return [place(cx + (i - (n - 1) / 2) * dx, cy) for i in range(n)]

        archs = []
        # A: domain. dots B, P, A, I (3 each) in domain boxes
        lines = VGroup(ln((0, 0), (-2.5, 1.35)), ln((0, 0), (2.5, 1.35)), ln((0, 0), (-2.5, -1.35)),
                       ln((0, 0), (2.5, -1.35)))
        boxes = VGroup(bx(0, 0, "Central gateway", 1.7), bx(-2.5, 1.35, "Body"), bx(2.5, 1.35, "Infotainment"),
                       bx(-2.5, -1.35, "Powertrain"), bx(2.5, -1.35, "ADAS"))
        dots = {"B": row(-2.5, 1.25, 3), "P": row(-2.5, -1.45, 3), "A": row(2.5, -1.45, 3), "I": row(2.5, 1.25, 3)}
        archs.append(("1  Domain", ["Grouped by function.", "The network mirrors the", "org chart. Sensors run to",
                                    "'their' domain, wherever", "it sits in the car."], lines, boxes, dots))
        # B: distributed compute
        lines = VGroup(*[ln((0, 0), p) for p in [(-3.1, 0), (3.1, 0), (0, 1.6), (0, -1.6), (-1.6, 1.15), (1.6, 1.15)]])
        boxes = VGroup(bx(0, 0, "Vehicle computer", 1.8), bx(-3.1, 0, "Zone front", 1.4), bx(3.1, 0, "Zone rear", 1.4),
                       bx(0, 1.6, "Zone right", 1.4), bx(0, -1.6, "Zone left", 1.4),
                       bx(-1.9, 1.2, "ADAS", 1.3), bx(1.9, 1.2, "Infotainment", 1.3))
        dots = {"B": [row(-3.1, -0.1, 1)[0], row(0, 1.5, 1)[0], row(0, -1.7, 1)[0]],
                "P": row(0, -0.1, 3), "A": row(-1.9, 1.1, 3), "I": row(1.9, 1.1, 3)}
        archs.append(("2  Distributed compute", ["Zones collect the I/O.", "A vehicle computer is", "added, ADAS and cockpit",
                                                "keep their own computers.", "Star-shaped backbone."], lines, boxes, dots))
        # C: distributed zonal
        lines = VGroup(ln((-3.1, 0), (-3.1, 1.75)), ln((-3.1, 1.75), (2.2, 1.75)), ln((-3.1, 0), (-3.1, -1.75)),
                       ln((-3.1, -1.75), (2.2, -1.75)), ln((2.2, 1.75), (2.2, 0), True), ln((2.2, -1.75), (2.2, 0), True),
                       ln((0, 0), (2.2, 0)), ln((-3.1, 0), (0, 0)))
        boxes = VGroup(bx(-3.1, 0, "HP zone front", 1.5, 0.9), bx(0.6, 1.55, "HP zone right", 1.6, 0.85),
                       bx(0.6, -1.55, "HP zone left", 1.6, 0.85), bx(-0.2, 0, "Central: cockpit + ADAS", 2.6, 1.0))
        dots = {"B": [place(-3.4, -0.12), place(0.3, 1.45), place(0.3, -1.65)],
                "P": [place(-2.9, -0.12), place(0.75, 1.45), place(0.75, -1.65)],
                "A": row(-0.65, -0.12, 3), "I": row(0.35, -0.12, 3)}
        archs.append(("3  Distributed zonal", ["Powerful zones also host", "functions of their area.", "Ring backbone: one broken",
                                              "link is survivable, but logic", "is spread over the car."], lines, boxes, dots))
        # D: consolidated
        zs = [(-3.1, 1.6), (0, 1.75), (3.1, 1.6), (-3.1, -1.6), (0, -1.75), (3.1, -1.6)]
        lines = VGroup(*[ln((0, 0), z) for z in zs], ln((-3.1, 1.6), (-3.1, -1.6), True, MUTED),
                       ln((3.1, 1.6), (3.1, -1.6), True, MUTED))
        boxes = VGroup(*[bx(x, y, "Aggregator", 1.3, 0.45, OK) for x, y in zs],
                       bx(0, 0, "Consolidated compute", 3.6, 1.5, OK))
        for b in boxes[:6]:
            b[1].move_to(b[0])
        d = row(0, 0.12, 6, 0.5) + row(0, -0.35, 6, 0.5)
        dots = {"B": d[0:3], "P": d[6:9], "A": d[3:6], "I": d[9:12]}
        archs.append(("4  Consolidated compute", ["All functions in one place,", "in isolated partitions.", "Zones only aggregate I/O.",
                                                 "The network is now part", "of every control loop."], lines, boxes, dots))

        D = {k: [Dot(radius=0.11, color=self.COL[k], z_index=5).move_to(p) for p in archs[0][4][k]] for k in "BPAI"}
        cur = None
        for i, (name, text, lines, boxes, dots) in enumerate(archs):
            t = fit(txt(name, 26, INK, True), 4.0).move_to([2.0, 1.75, 0], aligned_edge=LEFT)
            body = VGroup(*[txt(s, 20, MUTED) for s in text]).arrange(DOWN, aligned_edge=LEFT, buff=0.13)
            body.next_to(t, DOWN, buff=0.35, aligned_edge=LEFT)
            new = VGroup(lines, boxes, t, body)
            alld = [x for k in "BPAI" for x in D[k]]
            if cur is None:
                self.play(FadeIn(new), *[FadeIn(x) for x in alld], run_time=0.8)
            else:
                self.play(FadeOut(cur), run_time=0.4)
                self.add(*alld)
                self.play(FadeIn(new), *[D[k][j].animate.move_to(dots[k][j]) for k in "BPAI" for j in range(3)],
                          run_time=1.3)
            cur = new
            self.wait(2.4)
        self.wait(1)


class FrameTypes(Scene):
    """Six frames from the sample capture, drawn to scale."""

    ROWS = [
        ("ARP request", "60 B", [("MACs", 12, GREY1), ("0806", 2, INK), ("ARP", 28, TEAL), ("padding", 18, None)],
         "who has 10.0.0.2?"),
        ("SOME/IP request", "60 B", [("MACs", 12, GREY1), ("0800", 2, INK), ("IPv4", 20, TEAL), ("UDP", 8, PURPLE),
                                     ("SOME/IP", 16, AMBER), ("", 2, None)], "call method 0x0001"),
        ("SOME/IP-SD offer", "98 B", [("MACs", 12, GREY1), ("0800", 2, INK), ("IPv4", 20, TEAL), ("UDP", 8, PURPLE),
                                      ("SOME/IP", 16, AMBER), ("SD entries + options", 40, BLUE)], "multicast"),
        ("Event in VLAN 10", "70 B", [("MACs", 12, GREY1), ("tag", 4, BAD), ("0800", 2, INK), ("IPv4", 20, TEAL),
                                      ("UDP", 8, PURPLE), ("SOME/IP", 16, AMBER), ("data", 8, BLUE)], "priority 5"),
        ("gPTP Sync", "60 B", [("MACs", 12, GREY1), ("88f7", 2, INK), ("PTP header", 34, BLUE), ("body", 10, BLUE),
                               ("", 2, None)], "no IP at all"),
        ("AVTP stream", "74 B", [("MACs", 12, GREY1), ("tag", 4, BAD), ("22f0", 2, INK), ("AVTP header", 24, BLUE),
                                 ("video data", 32, OK)], "no IP, priority 3"),
    ]

    def construct(self):
        header(self, "Six frames, one envelope",
               "Real frames from the sample capture, to scale. The first bytes always look the same, then the paths split.")
        footer(self, ["Black    EtherType: tells the receiver which protocol follows · red: 802.1Q VLAN tag, 4 bytes",
                      "Capture  starts at the destination MAC; preamble and FCS are handled by the hardware · dashed = padding"])
        x0, unit = -4.3, 8.3 / 98
        ys = [1.75 - i * 0.82 for i in range(6)]
        marks = VGroup()
        for (name, size, fields, why), y in zip(self.ROWS, ys):
            lab = VGroup(txt(name, 18, INK, True), mono(size, 13)).arrange(DOWN, aligned_edge=LEFT, buff=0.05)
            lab.move_to([-6.75, y, 0], aligned_edge=LEFT)
            self.play(FadeIn(lab), run_time=0.2)
            x, anims = x0, []
            for n, b, c in fields:
                w = b * unit
                if c is None:
                    r = DashedVMobject(Rectangle(width=w, height=0.42, stroke_color=MUTED, stroke_width=1.5),
                                       num_dashes=max(8, int(b * 2)))
                    tc = MUTED
                else:
                    r = Rectangle(width=w, height=0.46, stroke_color=BG, stroke_width=1.5, fill_color=c, fill_opacity=1)
                    tc = "#ffffff"
                r.move_to([x + w / 2, y, 0])
                g = VGroup(r)
                if n and c != INK:
                    g.add(fit(txt(n, 14, tc, True), w - 0.06).move_to(r))
                if c == INK:
                    g.add(mono("0x" + n, 12, INK).next_to(r, UP, buff=0.04))
                    marks.add(r)
                anims.append(FadeIn(g, shift=RIGHT * 0.1))
                x += w
            w = txt(why, 16, MUTED).move_to([x + 0.2, y, 0], aligned_edge=LEFT)
            self.play(LaggedStart(*anims, lag_ratio=0.35), run_time=1.0)
            self.play(FadeIn(w), run_time=0.25)
            self.wait(0.35)
        self.play(*[Indicate(m, scale_factor=1.6, color=BAD) for m in marks], run_time=1.2)
        self.wait(2.5)


class _Star(Scene):
    """Four ECUs around one switch, used by the L2 scenes."""

    def star(self, names=True):
        self.P = {"gateway": LEFT * 5.0 + UP * 1.2, "camera": LEFT * 5.0 + DOWN * 1.5,
                  "brake": RIGHT * 0.6 + UP * 1.2, "tester": RIGHT * 0.6 + DOWN * 1.5}
        self.SW = np.array([-2.2, -0.15, 0])
        sub = {"gateway": "10.0.0.1  :01", "camera": "10.0.0.2  :02", "brake": "10.0.0.3  :03",
               "tester": "10.0.0.100  :64"}
        self.links = VGroup(*[Line(self.SW, p, stroke_color=GRID, stroke_width=4) for p in self.P.values()])
        self.boxes = {k: box(p, k.capitalize(), sub[k], 2.0, 0.85) for k, p in self.P.items()}
        self.sw = box(self.SW, "Switch", None, 1.4, 0.7, INK)
        self.add(self.links, *self.boxes.values(), self.sw)

    def near(self, ecu):
        """Parking position of a packet: next to the ECU on its link, so that the names stay readable."""
        return self.P[ecu] + 0.45 * (self.SW - self.P[ecu])

    def send(self, path, label, c=BLUE, rt=0.9):
        pts = [self.SW + DOWN * 0.62 if p == "sw" else self.near(p) for p in path]
        k = pkt(label, c)
        k.set_z_index(10).move_to(pts[0])
        self.add(k)
        for q in pts[1:]:
            self.play(k.animate.move_to(q), run_time=rt)
        return k

    def flood(self, src, label, c=BLUE, rt=0.9, dim=()):
        k = self.send([src, "sw"], label, c, rt)
        ks = {d: k.copy() for d in self.P if d != src}
        self.remove(k)
        self.add(*ks.values())
        self.play(*[m.animate.move_to(self.near(d)) for d, m in ks.items()], run_time=rt)
        return ks

    def table(self, title, rows, y=1.75):
        g = VGroup(txt(title, 18, INK, True))
        for r, c in rows:
            g.add(mono(r, 16, c))
        g.arrange(DOWN, aligned_edge=LEFT, buff=0.14)
        g.move_to([2.4, y, 0], aligned_edge=UL)
        return g

    def step(self, s, old=None, c=INK):
        n = fit(txt(s, 20, c, True), 12.8).move_to([0, -2.5, 0])
        self.play(*([FadeOut(old)] if old else []), FadeIn(n), run_time=0.35)
        return n


class SwitchLearning(_Star):
    """A switch floods, learns, forwards, and can be fooled."""

    def construct(self):
        header(self, "How a switch learns, and how it is fooled",
               "It remembers behind which port it last saw a source address. That table is called the FDB.")
        footer(self, ["Vehicle  topology is fixed: static FDB entries, learning limited or off, VLANs per port",
                      "Lab      on a Linux bridge, 'static' alone did not hold, 'static sticky' did: measure the protection"])
        self.star()
        tab = self.table("Switch: FDB", [("(empty)", MUTED)])
        self.add(tab)

        def upd(rows):
            nonlocal tab
            new = self.table("Switch: FDB", rows)
            self.play(FadeOut(tab), FadeIn(new), run_time=0.35)
            tab = new

        s = self.step("1  Camera sends to the brake (:03). The switch doesn't know :03 yet: it floods.")
        ks = self.flood("camera", "to :03")
        upd([(":02  behind port camera", OK)])
        self.wait(0.8)
        self.play(*[FadeOut(m) for m in ks.values()], run_time=0.3)
        s = self.step("2  The brake sends once. Its source address is enough: the switch has learned.", s)
        k = self.send(["brake", "sw", "camera"], "from :03")
        upd([(":02  behind port camera", INK), (":03  behind port brake", OK)])
        self.play(FadeOut(k), run_time=0.2)
        s = self.step("3  Now the same frame reaches the brake only.", s)
        k = self.send(["camera", "sw", "brake"], "to :03")
        self.wait(0.6)
        self.play(FadeOut(k), run_time=0.2)
        s = self.step("4  The tester sends one frame with the brake's source address ...", s, BAD)
        k = self.send(["tester", "sw"], "from :03 (forged)", BAD)
        upd([(":02  behind port camera", INK), (":03  behind port tester", BAD)])
        self.play(FadeOut(k), run_time=0.2)
        s = self.step("... and the next brake command goes to the tester. The brake gets nothing.", s, BAD)
        k = self.send(["camera", "sw", "tester"], "brake command")
        self.wait(2.5)


class ArpResolution(_Star):
    """What happens before the first ping: ARP request, reply, cache, and only then the packet."""

    def construct(self):
        header(self, "ARP: from an IP address to a MAC address",
               "The camera wants to reach 10.0.0.1 in its own network, but Ethernet can only deliver to a MAC address.")
        footer(self, ["Request  42 B, to ff:ff:ff:ff:ff:ff: every device has to look at it",
                      "Reply    42 B, straight to the camera · nobody checks whether the answer is true"])
        self.star()
        tabs = {}

        def put(name, title, row, c, y):
            new = self.table(title, [(row, c)], y)
            if name in tabs:
                self.play(FadeOut(tabs[name]), FadeIn(new), run_time=0.3)
            else:
                self.play(FadeIn(new), run_time=0.25)
            tabs[name] = new

        put("c", "Camera: neighbor cache", "(empty)", MUTED, 1.9)
        put("g", "Gateway: neighbor cache", "(empty)", MUTED, 0.75)
        put("b", "Brake: neighbor cache", "(empty)", MUTED, -0.4)
        s = self.step("1  The IP packet is ready, but the MAC address is unknown: the packet has to wait.")
        held = pkt("IP packet", AMBER).move_to(self.P["camera"] + DOWN * 0.65)
        self.play(FadeIn(held), run_time=0.4)
        put("c", "Camera: neighbor cache", "10.0.0.1 -> ?  INCOMPLETE", AMBER, 1.9)
        s = self.step("2  Broadcast: \"Who has 10.0.0.1? Tell 10.0.0.2, I am :02.\"", s)
        ks = self.flood("camera", "who has .1?", BLUE, 1.0)
        self.wait(0.5)
        self.play(ks["brake"].animate.set_opacity(0.25), ks["tester"].animate.set_opacity(0.25), run_time=0.4)
        put("g", "Gateway: neighbor cache", "10.0.0.2 -> :02  DELAY", OK, 0.75)
        s = self.step("3  Only the gateway is meant. It has learned the camera from the question itself.", s)
        self.wait(0.8)
        self.play(*[FadeOut(m) for m in ks.values()], run_time=0.3)
        s = self.step("4  Unicast reply: \"10.0.0.1 is at :01.\"", s)
        k = self.send(["gateway", "sw", "camera"], ".1 is at :01", OK, 1.0)
        put("c", "Camera: neighbor cache", "10.0.0.1 -> :01  REACHABLE", OK, 1.9)
        self.play(FadeOut(k), run_time=0.2)
        s = self.step("5  Now the waiting packet leaves, addressed to :01.", s)
        self.remove(held)
        k = self.send(["camera", "sw", "gateway"], "IP packet", AMBER, 1.0)
        self.wait(0.5)
        warn = fit(txt("AUTOSAR may drop the waiting packet", 17, BAD, True), 4.2).move_to([2.4, -1.5, 0], aligned_edge=LEFT)
        w2 = fit(txt("instead: the first signal is lost", 17, BAD), 4.2).next_to(warn, DOWN, buff=0.08, aligned_edge=LEFT)
        self.play(FadeIn(warn), FadeIn(w2), run_time=0.4)
        self.wait(3)


class RouterHop(Scene):
    """Camera to brake through the gateway: MACs change on each hop, IPs stay."""

    def construct(self):
        header(self, "Through the gateway: new envelope, same letter",
               "Camera 10.0.0.2 sends to the brake in VLAN 10. The gateway routes between the two networks.")
        footer(self, ["Switch  looks at MAC addresses, changes nothing",
                      "Router  looks at IP addresses, removes the Ethernet header, lowers the TTL, builds a new header"])
        xs = [-5.2, 0, 5.2]
        y = 1.2
        nm = [("Camera", "10.0.0.2  :02"), ("Gateway", ":01"), ("Brake", "10.0.10.3  :03")]
        bs = [box([x, y, 0], n, s, 2.3, 0.9) for x, (n, s) in zip(xs, nm)]
        l1 = Line(bs[0].get_right(), bs[1].get_left(), stroke_color=GRID, stroke_width=5)
        l2 = Line(bs[1].get_right(), bs[2].get_left(), stroke_color=BAD, stroke_width=5)
        self.add(l1, l2, *bs, mono("untagged", 14).next_to(l1, UP, buff=0.1), mono("VLAN 10", 14, BAD).next_to(l2, UP, buff=0.1))

        def letter(mac, vlan, ttl):
            rows = [("MAC", mac, GREY1)]
            if vlan:
                rows.append(("VLAN", vlan, BAD))
            rows += [("IP", "10.0.0.2 → 10.0.10.3", TEAL), ("TTL", ttl, PURPLE)]
            g = VGroup()
            for a, b, c in rows:
                r = Rectangle(width=3.6, height=0.42, stroke_color=BG, stroke_width=2, fill_color=c, fill_opacity=1)
                t = VGroup(txt(a, 16, "#ffffff", True), mono(b, 16, "#ffffff")).arrange(RIGHT, buff=0.2).move_to(r)
                g.add(VGroup(r, t))
            return g.arrange(DOWN, buff=0)

        a = letter(":02 → :01", None, "64").move_to([xs[0] + 0.4, -0.6, 0])
        self.play(FadeIn(a), run_time=0.5)
        s1 = txt("1  IP target is the brake, MAC target is the next hop: the gateway.", 20, INK, True).move_to([0, -2.45, 0])
        self.play(FadeIn(s1), run_time=0.3)
        self.wait(1.2)
        self.play(a.animate.move_to([0, -0.6, 0]), run_time=1.4)
        s2 = txt("2  The gateway throws the Ethernet header away and checks its routing table.", 20, INK, True).move_to([0, -2.45, 0])
        self.play(FadeOut(s1), FadeIn(s2), a[0].animate.set_opacity(0.15), run_time=0.6)
        self.wait(1.2)
        b = letter(":01 → :03", "10", "63").move_to([0, -0.6, 0])
        s3 = txt("3  New Ethernet header with VLAN tag, TTL 63. The IP addresses did not change.", 20, INK, True).move_to([0, -2.45, 0])
        self.play(FadeOut(a), FadeIn(b), FadeOut(s2), FadeIn(s3), run_time=0.7)
        self.play(Indicate(b[0], color=GREY1), Indicate(b[1], color=BAD), Indicate(b[3], color=PURPLE), run_time=1.0)
        self.play(b.animate.move_to([xs[2] - 0.4, -0.6, 0]), run_time=1.4)
        self.wait(2.5)


class ServiceDiscovery(Scene):
    """Offer, subscribe, ack, events, then the server disappears and the TTL runs out."""

    def construct(self):
        header(self, "SOME/IP service discovery: offer, subscribe, expire",
               "The brake offers service 0x1001. Everything that is agreed expires after its TTL unless it is renewed.")
        footer(self, ["Offer      multicast 224.244.224.245, UDP port 30490 · says where the service is: 10.0.0.3:30501",
                      "Subscribe  unicast to the server, with the address the events should go to: 10.0.0.2:30501"])
        xl, xr, top, bot = -3.4, 3.4, 1.65, -2.35
        cb, bb = box([xl, 2.0, 0], "Camera", "client", 2.0, 0.65), box([xr, 2.0, 0], "Brake", "server", 2.0, 0.65)
        self.add(Line([xl, top, 0], [xl, bot, 0], stroke_color=GRID, stroke_width=3),
                 Line([xr, top, 0], [xr, bot, 0], stroke_color=GRID, stroke_width=3), cb, bb)
        y = [1.25]

        def msg(to_left, label, c, dash=False):
            a, b = ([xr, y[0], 0], [xl, y[0] - 0.12, 0]) if to_left else ([xl, y[0], 0], [xr, y[0] - 0.12, 0])
            ar = Arrow(a, b, buff=0.05, color=c, stroke_width=4, max_tip_length_to_length_ratio=0.04)
            t = txt(label, 17, c, True).move_to([0, y[0] + 0.14, 0])
            self.play(GrowArrow(ar), FadeIn(t), run_time=0.75)
            y[0] -= 0.5

        def side(s, left, c=MUTED, dy=0.35):
            t = VGroup(*[txt(q, 16, c, c != MUTED) for q in s.split("\n")]).arrange(DOWN, buff=0.06, aligned_edge=LEFT)
            t.move_to([xl - 0.25 if left else xr + 0.25, y[0] + dy, 0], aligned_edge=RIGHT if left else LEFT)
            self.play(FadeIn(t), run_time=0.3)

        msg(True, "OfferService 0x1001, TTL 3 s  (multicast)", BLUE)
        side("now I know where:\n10.0.0.3:30501", True)
        msg(False, "SubscribeEventgroup 1, TTL 3 s", PURPLE)
        side("note: group 1 goes\nto 10.0.0.2:30501", False)
        msg(True, "SubscribeEventgroupAck", PURPLE)
        msg(True, "Event 0x8001, session 1: 200", OK)
        msg(True, "Event 0x8001, session 2: 210", OK)
        self.wait(0.4)
        x = Cross(bb, stroke_color=BAD, stroke_width=5)
        self.play(Create(x), run_time=0.5)
        side("cable off, no\ngoodbye message", False, BAD, 0.1)
        y[0] -= 0.15
        clock = VGroup()
        for i in (3, 2, 1, 0):
            t = txt(f"TTL: {i} s left" if i else "TTL expired: service gone, use the substitute value", 20,
                    BAD if i == 0 else AMBER, True).move_to([0, y[0], 0])
            self.play(FadeIn(t), run_time=0.2)
            self.wait(0.55)
            if i:
                self.remove(t)
        self.wait(2.5)


class GptpSync(Scene):
    """Four timestamps give the link delay, two more give the clock offset."""

    def construct(self):
        header(self, "gPTP: measure the path, then set the clock",
               "The camera's clock is 5000 ns behind. Neither side knows that at the start.")
        footer(self, ["Trick       each side only subtracts its own timestamps, so the offset cancels out",
                      "Assumption  the way there takes as long as the way back; any asymmetry ends up halved in the result"])
        xl, xr = -4.6, 0.9
        self.add(box([xl, 2.0, 0], "Camera", "slave", 1.8, 0.65), box([xr, 2.0, 0], "Gateway", "grandmaster", 1.8, 0.65),
                 Line([xl, 1.65, 0], [xl, -2.45, 0], stroke_color=GRID, stroke_width=3),
                 Line([xr, 1.65, 0], [xr, -2.45, 0], stroke_color=GRID, stroke_width=3))

        def stamp(x, y, s, left, c=INK):
            d = Dot([x, y, 0], radius=0.07, color=c)
            t = mono(s, 15, c).next_to(d, LEFT if left else RIGHT, buff=0.12)
            return VGroup(d, t)

        def arrow(x1, y1, x2, y2, label, c):
            a = Arrow([x1, y1, 0], [x2, y2, 0], buff=0.05, color=c, stroke_width=4, max_tip_length_to_length_ratio=0.05)
            t = txt(label, 16, c, True).move_to([(x1 + x2) / 2, (y1 + y2) / 2 + 0.22, 0])
            return a, t

        def go(*args):
            a, t = arrow(*args)
            self.play(GrowArrow(a), FadeIn(t), run_time=0.7)

        def calc(lines, y):
            g = VGroup(*[fit(txt(s, 18, c, b), 4.2) for s, c, b in lines]).arrange(DOWN, aligned_edge=LEFT, buff=0.12)
            g.move_to([2.55, y, 0], aligned_edge=UL)
            self.play(LaggedStart(*[FadeIn(m) for m in g], lag_ratio=0.6), run_time=1.6)

        s1, s2, s3, s4 = (stamp(xl, 1.3, "t1 = 100", True), stamp(xr, 1.1, "t2 = 5125", False),
                          stamp(xr, 0.7, "t3 = 5525", False), stamp(xl, 0.5, "t4 = 550", True))
        self.play(FadeIn(s1), run_time=0.3)
        go(xl, 1.3, xr, 1.1, "Pdelay_Req", BLUE)
        self.play(FadeIn(s2), run_time=0.3)
        self.play(FadeIn(s3), run_time=0.3)
        go(xr, 0.7, xl, 0.5, "Pdelay_Resp", BLUE)
        self.play(FadeIn(s4), run_time=0.3)
        go(xr, 0.1, xl, -0.1, "Pdelay_Resp_Follow_Up (t3)", BLUE)
        calc([("Step 1: link delay", BLUE, True), ("round trip  550 - 100 = 450", INK, False),
              ("turnaround  5525 - 5125 = 400", INK, False), ("(450 - 400) / 2 = 25 ns", BLUE, True)], 1.75)
        self.wait(1.0)
        m1, m2 = stamp(xr, -0.75, "10000", False), stamp(xl, -0.95, "5025", True)
        self.play(FadeIn(m1), run_time=0.3)
        go(xr, -0.75, xl, -0.95, "Sync", OK)
        self.play(FadeIn(m2), run_time=0.3)
        go(xr, -1.5, xl, -1.7, "Follow_Up: \"Sync left at 10000\"", OK)
        calc([("Step 2: clock offset", OK, True), ("received - sent - delay", INK, False),
              ("5025 - 10000 - 25", INK, False), ("= -5000 ns: 5 µs behind", OK, True)], -0.55)
        self.wait(3)


class GptpBridges(Scene):
    """Time-aware bridges add residence time and link delay to the correction."""

    def construct(self):
        header(self, "gPTP across switches: everyone adds their share",
               "Each switch measures how long the time message was under way and passes the sum on.")
        footer(self, ["Link       measured with Pdelay on every port, all the time",
                      "Residence  how long the message stayed in the switch · rate differences of the clocks are corrected too"])
        xs = [-5.6, -1.9, 1.9, 5.6]
        nm = [("Gateway", "grandmaster"), ("Switch A", "+ 2000 ns"), ("Switch B", "+ 3000 ns"), ("Camera", "slave")]
        bs = [box([x, 0.9, 0], n, s, 1.9, 0.9) for x, (n, s) in zip(xs, nm)]
        ld = [25, 30, 20]
        ls = [Line(bs[i].get_right(), bs[i + 1].get_left(), stroke_color=GRID, stroke_width=5) for i in range(3)]
        self.add(*ls, *bs, *[mono(f"{d} ns", 15).next_to(l, DOWN, buff=0.12) for d, l in zip(ld, ls)])
        add = [25, 2000, 30, 3000, 20]
        col = [BLUE, AMBER, BLUE, AMBER, BLUE]
        lab = ["link 25", "switch A 2000", "link 30", "switch B 3000", "link 20"]
        dest = [xs[1], xs[1], xs[2], xs[2], xs[3]]
        k = pkt("Sync", OK).move_to([xs[0], 1.75, 0])
        self.play(FadeIn(k), run_time=0.3)
        total, cur = 0, txt("correction: 0 ns", 26, INK, True).move_to([0, -0.5, 0])
        self.play(FadeIn(cur), run_time=0.3)
        # stacked bar, links exaggerated so that they stay visible
        wv = [0.5, 3.4, 0.5, 5.1, 0.5]
        x = -5.0
        for i in range(5):
            total += add[i]
            if i % 2 == 0:
                self.play(k.animate.move_to([dest[i], 1.75, 0]), run_time=0.9)
            r = Rectangle(width=wv[i], height=0.45, stroke_color=BG, stroke_width=2, fill_color=col[i],
                          fill_opacity=1).move_to([x + wv[i] / 2, -1.35, 0])
            t = mono(lab[i], 13).next_to(r, DOWN, buff=0.1)
            x += wv[i]
            new = txt(f"correction: {total} ns", 26, INK, True).move_to([0, -0.5, 0])
            self.play(GrowFromEdge(r, LEFT), FadeIn(t), FadeOut(cur), FadeIn(new), run_time=0.7)
            cur = new
            self.wait(0.3)
        n = note("The grandmaster's time plus 5075 ns is the time at the camera. A switch that doesn't take part would hide its 2000 ns.",
                 -2.4, MUTED, 18)
        self.play(FadeIn(n), run_time=0.4)
        self.wait(2.8)


class CreditBasedShaper(Scene):
    """Credit of one shaped queue: sawtooth, a foreign frame, and an empty queue."""

    def construct(self):
        header(self, "Credit-based shaper: a frame starts only at credit 0 or above",
               "A burst of five camera frames (1046 bytes) on 100BASE-T1, with 8 Mbit/s reserved. Calculated, without preamble and gap.")
        footer(self, ["idleSlope   +8 Mbit/s = +1 byte/us     while a frame waits, or while a negative credit recovers",
                      "sendSlope   8 - 100 = -92 Mbit/s = -11.5 byte/us     while a frame of this queue is sent"])
        x0, sx, y0, sy = -5.0, 10.9 / 5800, 1.2, 2.3 / 1000
        yw = -2.05

        def P(t, c):
            return np.array([x0 + t * sx, y0 + c * sy, 0])

        self.add(Line(P(0, 0), P(5800, 0), stroke_color=GRID, stroke_width=2),
                 Line(P(0, -1100), P(0, 330), stroke_color=MUTED, stroke_width=2),
                 Line([x0, yw - 0.22, 0], [x0 + 5800 * sx, yw - 0.22, 0], stroke_color=GRID, stroke_width=2))
        for c, s in ((0, "0"), (123, "+123"), (-962, "-962")):
            self.add(mono(s, 14).move_to(P(0, c) + LEFT * 0.12, aligned_edge=RIGHT))
        self.add(txt("credit (bytes)", 16, INK).move_to(P(0, 300) + RIGHT * 0.15, aligned_edge=LEFT),
                 txt("on the wire", 16, INK).move_to([x0 - 0.15, yw, 0], aligned_edge=RIGHT))
        for k in range(6):
            self.add(DashedLine(P(1046 * k, -1060), [x0 + 1046 * k * sx, yw - 0.25, 0], stroke_color=GRID, stroke_width=1.5),
                     mono(f"{1046 * k} us", 13).move_to([x0 + 1046 * k * sx, yw - 0.42, 0]))
        dot = Dot(P(0, 0), radius=0.08, color=INK)
        self.add(dot)

        def seg(a, b, c, rt, *extra):
            ln = Line(P(*a), P(*b), stroke_color=c, stroke_width=5)
            self.play(Create(ln), dot.animate.move_to(P(*b)), *extra, run_time=rt, rate_func=linear)
            self.bring_to_front(dot)

        def wire(t0, t1, c, label):
            r = Rectangle(width=(t1 - t0) * sx, height=0.4, stroke_width=0, fill_color=c, fill_opacity=1).move_to(
                [x0 + (t0 + t1) / 2 * sx, yw, 0])
            return VGroup(r, txt(label, 13, "#ffffff", True).move_to(r))

        def send(t, c, n, rt=0.6):
            seg((t, c), (t + 84, c - 962), BAD, rt, FadeIn(wire(t, t + 84, BLUE, str(n))))

        say = None

        def tell(s, c=INK):
            nonlocal say
            t = fit(txt(s, 20, c, True), 12.8).move_to([0.4, 2.25, 0])
            if say is None:
                self.play(FadeIn(t), run_time=0.3)
            else:
                self.play(FadeOut(say), FadeIn(t), run_time=0.3)
            say = t

        tell("Sending: the credit falls steeply with the sendSlope", BAD)
        send(0, 0, 1, 1.0)
        tell("Waiting: the credit recovers slowly with the idleSlope", OK)
        seg((84, -962), (1046, 0), OK, 1.8)
        send(1046, 0, 2)
        seg((1130, -962), (2092, 0), OK, 1.2)
        tell("A foreign frame occupies the wire: the waiting queue earns extra credit", AMBER)
        seg((2092, 0), (2215, 123), AMBER, 1.2, FadeIn(wire(2092, 2215, GREY1, "")))
        tell("Frame 3 starts late, but with +123. It needs less time to recover", INK)
        send(2215, 123, 3)
        seg((2299, -839), (3138, 0), OK, 1.3)
        tell("Frame 4 is on time again: the delay has been made up", OK)
        send(3138, 0, 4)
        seg((3222, -962), (4184, 0), OK, 0.9)
        send(4184, 0, 5)
        tell("The queue is empty: recovery stops at 0, nothing can be saved up", PURPLE)
        seg((4268, -962), (5230, 0), OK, 0.9)
        seg((5230, 0), (5800, 0), PURPLE, 0.8)
        self.wait(2.5)


class TimeAwareShaper(Scene):
    """Same gate schedule, two senders: one ignores it, one is aligned to it."""

    def construct(self):
        header(self, "A time window only helps a sender that knows the clock",
               "The gate for class 1 is open for 10 ms in every 100 ms, as in the lab (real schedules are closer to 1 ms).")
        footer(self, ["Not aligned  the camera sends every 13 ms: frames wait for the next window, here up to 86 ms",
                      "Aligned      sender, switches and schedule share gPTP time: frames are ready just before the gate opens"])
        x0, sc = -4.9, 10.9 / 320

        def X(t):
            return x0 + t * sc

        def lane(y, name):
            return VGroup(Line([X(0), y, 0], [X(320), y, 0], stroke_color=GRID, stroke_width=2),
                          txt(name, 16, INK).move_to([X(0) - 0.15, y, 0], aligned_edge=RIGHT))

        ya, yb, yc, yd = 1.35, 0.5, -0.75, -1.6
        self.add(txt("Not aligned", 19, BAD, True).move_to([X(0), 1.95, 0], aligned_edge=LEFT),
                 txt("Aligned", 19, OK, True).move_to([X(0), -0.2, 0], aligned_edge=LEFT))
        self.add(lane(ya, "sender ready"), lane(yb, "on the wire"), lane(yc, "sender ready"), lane(yd, "on the wire"))
        for t in (0, 100, 200, 300):
            for top, bottom in ((ya + 0.3, yb - 0.3), (yc + 0.3, yd - 0.3)):
                self.add(Rectangle(width=10 * sc, height=top - bottom, stroke_width=0, fill_color=OK,
                                   fill_opacity=0.22).move_to([X(t + 5), (top + bottom) / 2, 0]))
            self.add(mono(f"{t} ms", 13).move_to([X(t + 5), yd - 0.5, 0]))

        def tick(t, y, c):
            return Rectangle(width=0.09, height=0.34, stroke_width=0, fill_color=c, fill_opacity=1).move_to([X(t), y, 0])

        arr = [14 + 13 * k for k in range(23)]
        # show a burst as ticks side by side (exaggerated), number above
        for cyc in (0, 1, 2):
            idx = [i for i, t in enumerate(arr) if cyc * 100 + (10 if cyc else 0) <= t < (cyc + 1) * 100 + 10]
            waits = [i for i in idx if arr[i] % 100 >= 10]
            direct = [i for i in idx if arr[i] % 100 < 10 and arr[i] >= 100]
            self.play(LaggedStart(*[FadeIn(tick(arr[i], ya, BLUE), shift=DOWN * 0.15) for i in waits], lag_ratio=0.4),
                      run_time=1.2)
            b = (cyc + 1) * 100
            grp = VGroup(*[tick(arr[i], ya, BLUE) for i in waits])
            self.add(grp)
            burst = VGroup(*[Rectangle(width=0.011, height=0.34, stroke_width=0, fill_color=BAD, fill_opacity=1)
                             .move_to([X(b) + 0.01 + n * 0.018, yb, 0]) for n in range(len(waits))])
            self.play(TransformFromCopy(grp, burst), run_time=0.7)
            q = txt(f"burst of {len(waits)}", 14, BAD, True).next_to(burst, DOWN, buff=0.16)
            self.play(FadeIn(q), *[FadeIn(tick(arr[i], ya, OK)) for i in direct],
                      *[FadeIn(tick(max(arr[i], b + 5.5), yb, OK)) for i in direct], run_time=0.4)
        worst = txt("waits up to 86 ms", 17, BAD, True).move_to([X(320), 1.95, 0], aligned_edge=RIGHT)
        self.play(FadeIn(worst), run_time=0.3)
        for t in (98, 198, 298):
            a = tick(t, yc, BLUE)
            self.play(FadeIn(a, shift=DOWN * 0.15), run_time=0.3)
            self.play(TransformFromCopy(a, tick(t + 2.5, yd, OK)), run_time=0.45)
        good = txt("waits 2 ms, every time", 17, OK, True).move_to([X(320), -0.2, 0], aligned_edge=RIGHT)
        self.play(FadeIn(good), run_time=0.3)
        self.wait(3)
