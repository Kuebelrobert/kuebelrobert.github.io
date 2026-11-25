#!/usr/bin/env python3
"""
Animations for the posts on CPU/GPU/NPU and on scheduling heterogeneous compute.

Same style as communication_scenes.py, autosar_threadx_scenes.py and security_scenes.py.
Text only (Pango), no LaTeX needed. All numbers in the scenes are illustrative.

Render all scenes (720p30) into assets/videos/scheduling/:
    python3 scripts/manim/render_all.py scheduling

Or a single scene:
    manim -qm scripts/manim/scheduling_scenes.py GangVsPipeline

Requires: manim (pip install manim; tested with manim 0.22 on Python 3.13).
"""
from manim import *

BG = "#fdfdfd"
INK = "#111111"
MUTED = "#52514e"
GRID = "#c9c7c1"
OK = "#0ca30c"
BAD = "#d03b3b"
BLUE = "#2a78d6"
AMBER = "#e09a00"
IDLE = "#b9b7b1"
SOFT = "#eceae4"

config.background_color = BG

FONT = "Helvetica Neue"


def txt(s, fs=24, c=INK, bold=False):
    return Text(s, font_size=fs, color=c, font=FONT, weight=BOLD if bold else NORMAL)


def mono(s, fs=18, c=MUTED):
    return Text(s, font_size=fs, color=c, font="Menlo")


def header(scene, title, sub):
    t = txt(title, 32, INK, True).to_corner(UL, buff=0.45)
    s = txt(sub, 20, MUTED).next_to(t, DOWN, buff=0.12, aligned_edge=LEFT)
    if s.width > 13.0:
        s.scale_to_fit_width(13.0)
    scene.add(t, s)
    return VGroup(t, s)


def footer(scene, lines):
    g = VGroup(*[mono(l) for l in lines]).arrange(DOWN, aligned_edge=LEFT, buff=0.1)
    if g.width > 13.2:
        g.scale_to_fit_width(13.2)
    g.to_corner(DL, buff=0.4)
    scene.add(g)
    return g


def seg(x0, x1, y, color, h=0.42, label=None, fs=16, text_color="#ffffff", opacity=1.0):
    r = Rectangle(width=x1 - x0, height=h, stroke_color=color, stroke_width=2,
                  fill_color=color, fill_opacity=opacity).move_to([(x0 + x1) / 2, y, 0])
    g = VGroup(r)
    if label:
        t = txt(label, fs, text_color, True).move_to(r)
        if t.width > r.width - 0.1:
            t.scale_to_fit_width(max(r.width - 0.1, 0.1))
        g.add(t)
    return g


def grow(g):
    """Animation that wipes a segment in from the left."""
    return GrowFromEdge(g, LEFT)


# ----------------------------------------------------------------- scenes ---
class ComputeArchitectures(Scene):
    """How a CPU, a GPU and an NPU spend their transistors on the same kind of job."""

    def construct(self):
        header(self, "CPU, GPU, NPU: three ways to spend transistors",
               "Same kind of job: lots of multiply-adds. A sketch of the idea, not of any real chip.")
        footer(self, ["CPU  few strong cores, big caches, every core runs its own instruction stream",
                      "GPU  many simple lanes, one instruction for a whole group of them",
                      "NPU  multiply-add array with fixed dataflow, built for exactly one kind of math"])

        cxs = [-4.6, 0.0, 4.6]
        names = ["CPU", "GPU", "NPU"]
        subs = ["few strong cores", "many simple lanes", "fixed dataflow array"]
        frames = VGroup()
        for x, n, s in zip(cxs, names, subs):
            frames.add(RoundedRectangle(width=4.1, height=3.2, corner_radius=0.15, stroke_color=GRID,
                                        stroke_width=2.5).move_to([x, -0.35, 0]),
                       txt(n, 28, INK, True).move_to([x, 2.15, 0]),
                       txt(s, 18, MUTED).move_to([x, 1.78, 0]))
        self.play(FadeIn(frames), run_time=0.6)

        # --- CPU: four cores, each with its own stream, and a cache bar
        cpu_c = -4.6
        pos = [(-0.55, 0.55), (0.55, 0.55), (-0.55, -0.45), (0.55, -0.45)]
        cores = VGroup(*[Square(0.9, stroke_color=MUTED, stroke_width=2.5, fill_color=BG, fill_opacity=1)
                         .move_to([cpu_c + dx, 0.12 + dy, 0]) for dx, dy in pos])
        tags = VGroup(*[mono(s, 13).move_to(c) for s, c in zip(["A", "B", "C", "D"], cores)])
        cache = Rectangle(width=2.9, height=0.3, stroke_color=AMBER, stroke_width=2, fill_color=AMBER,
                          fill_opacity=0.25).move_to([cpu_c, -1.15, 0])
        cache_t = mono("large caches", 13).move_to(cache)
        cpu_note = txt("branch prediction · out-of-order", 14, MUTED).move_to([cpu_c, -1.5, 0])
        self.play(FadeIn(cores), FadeIn(tags), FadeIn(cache), FadeIn(cache_t), FadeIn(cpu_note), run_time=0.5)
        self.play(frames[0].animate.set_stroke(BLUE, 4), run_time=0.2)
        for _ in range(2):
            self.play(LaggedStart(*[c.animate.set_fill(BLUE, 0.9) for c in cores], lag_ratio=0.45),
                      run_time=1.0)
            self.play(LaggedStart(*[c.animate.set_fill(BG, 1) for c in cores], lag_ratio=0.3), run_time=0.7)
        self.play(frames[0].animate.set_stroke(GRID, 2.5), run_time=0.2)

        # --- GPU: 4 rows x 8 lanes, a row executes one instruction at a time
        gx = 0.0
        lanes = [[Square(0.34, stroke_color=MUTED, stroke_width=1.5, fill_color=BG, fill_opacity=1)
                  .move_to([gx + (j - 3.5) * 0.43, 0.75 - i * 0.43, 0]) for j in range(8)] for i in range(4)]
        allg = VGroup(*[s for row in lanes for s in row])
        gnote = txt("warps of lanes, thousands in flight", 14, MUTED).move_to([gx, -1.5, 0])
        self.play(FadeIn(allg), FadeIn(gnote), frames[3].animate.set_stroke(BLUE, 4), run_time=0.5)
        for i in range(4):
            self.play(*[s.animate.set_fill(BLUE, 0.9) for s in lanes[i]], run_time=0.35)
        # divergence: half of the lanes of row 1 have to wait while the other half take the branch
        div = txt("branch divergence: half the lanes wait", 15, BAD).move_to([gx, -1.2, 0])
        self.play(*[s.animate.set_fill(BG, 1) for row in lanes for s in row], run_time=0.3)
        self.play(*[s.animate.set_fill(BLUE, 0.9) for s in lanes[1][:4]],
                  *[s.animate.set_fill(IDLE, 0.9) for s in lanes[1][4:]], FadeIn(div), run_time=0.6)
        self.wait(0.6)
        self.play(*[s.animate.set_fill(BG, 1) for row in lanes for s in row], FadeOut(div),
                  frames[3].animate.set_stroke(GRID, 2.5), run_time=0.4)

        # --- NPU: 4x4 array, a wavefront of data crosses it
        nx = 4.6
        cells = [[Square(0.46, stroke_color=MUTED, stroke_width=2, fill_color=BG, fill_opacity=1)
                  .move_to([nx + (j - 1.5) * 0.6 + 0.15, 0.82 - i * 0.56, 0]) for j in range(4)] for i in range(4)]
        allc = VGroup(*[c for row in cells for c in row])
        arrows_in = VGroup(*[Arrow([nx - 1.7, 0.82 - i * 0.56, 0], [nx - 1.15, 0.82 - i * 0.56, 0], buff=0,
                                   stroke_width=3, color=BLUE, max_tip_length_to_length_ratio=0.5)
                             for i in range(4)])
        nnote = txt("weights stay in place, data flows through", 14, MUTED).move_to([nx, -1.57, 0])
        mac = mono("each cell: multiply-add", 13).move_to([nx, -1.27, 0])
        self.play(FadeIn(allc), FadeIn(arrows_in), FadeIn(nnote), FadeIn(mac),
                  frames[6].animate.set_stroke(BLUE, 4), run_time=0.5)
        for d in range(7):
            diag = [cells[i][d - i] for i in range(4) if 0 <= d - i < 4]
            self.play(*[c.animate.set_fill(BLUE, 0.9) for c in diag], run_time=0.3)
        self.wait(0.5)
        self.play(frames[6].animate.set_stroke(GRID, 2.5), run_time=0.2)

        # --- close with the trade-off
        tr = VGroup(
            txt("latency + flexibility", 17, INK, True).move_to([cxs[0], -1.85, 0]),
            txt("throughput on parallel work", 17, INK, True).move_to([cxs[1], -1.85, 0]),
            txt("efficiency on supported ops", 17, INK, True).move_to([cxs[2], -1.85, 0]))
        # keep the bottom labels clear of the footer
        for t in tr:
            t.set_y(-2.15)
        self.play(FadeIn(tr), run_time=0.5)
        self.wait(2.5)


class LatencyVsThroughput(Scene):
    """Why small jobs stay on the CPU and large ones go to an accelerator (illustrative shapes)."""

    def construct(self):
        header(self, "When is an accelerator worth the trip?",
               "Time to finish N work items. Offsets are launch and data transfer, slopes are the work itself.")
        footer(self, ["Illustrative shapes, not measurements. Real curves depend on the chip, the model and the memory traffic.",
                      "An operator the NPU doesn't support falls back to the CPU, and the offset comes back."])

        ax = Axes(x_range=[0, 100, 25], y_range=[0, 100, 25], x_length=9.0, y_length=3.6,
                  axis_config={"include_ticks": False, "include_numbers": False, "color": MUTED,
                               "stroke_width": 3, "tip_width": 0.15, "tip_height": 0.15},
                  tips=True).move_to([0.0, -0.2, 0])
        xl = txt("number of work items (batch size)", 18, MUTED).next_to(ax, DOWN, buff=0.15)
        yl = txt("time to finish", 18, MUTED).rotate(PI / 2).next_to(ax, LEFT, buff=0.2)
        self.play(Create(ax), FadeIn(xl), FadeIn(yl), run_time=0.8)

        def line(f, color, name, pos_x):
            g = ax.plot(f, x_range=[0, 100], color=color, stroke_width=5)
            lab = txt(name, 20, color, True).move_to(ax.c2p(pos_x, f(pos_x)) + UP * 0.3)
            return g, lab

        cpu, cpu_l = line(lambda x: min(1.0 * x, 100), BLUE, "CPU", 85)
        gpu, gpu_l = line(lambda x: 30 + 0.1 * x, AMBER, "GPU", 90)
        npu, npu_l = line(lambda x: 14 + 0.05 * x, OK, "NPU (supported ops)", 70)
        # keep labels from sitting on top of the lines
        cpu_l.move_to(ax.c2p(70, 70) + LEFT * 0.7 + UP * 0.1)
        gpu_l.move_to(ax.c2p(80, 38) + UP * 0.35)
        npu_l.move_to(ax.c2p(80, 18) + DOWN * 0.45)

        self.play(Create(cpu), FadeIn(cpu_l), run_time=1.0)
        self.play(Create(gpu), FadeIn(gpu_l), run_time=1.0)
        self.play(Create(npu), FadeIn(npu_l), run_time=1.0)

        x_cn = 14 / 0.95          # CPU = NPU
        x_cg = 30 / 0.9           # CPU = GPU
        d1 = Dot(ax.c2p(x_cn, x_cn), color=INK, radius=0.07)
        d2 = Dot(ax.c2p(x_cg, x_cg), color=INK, radius=0.07)
        t_small = txt("small jobs: the CPU is done\nbefore the others have started", 17, BLUE, True)
        t_small.move_to(ax.c2p(27, 76))
        t_large = txt("large jobs: the trip pays off", 17, OK, True).move_to(ax.c2p(27, 60))
        self.play(FadeIn(d1), FadeIn(d2), FadeIn(t_small), run_time=0.5)
        self.wait(0.8)
        self.play(FadeIn(t_large), run_time=0.5)
        self.wait(2.5)


class GangVsPipeline(Scene):
    """Gang scheduling vs. an uncoordinated barrier, and why a sensor pipeline is a different problem."""

    X0, S = -4.9, 1.0             # x at t = 0, units per time unit

    def X(self, t):
        return self.X0 + t * self.S

    def lanes(self, ys, names):
        g = VGroup()
        for y, n in zip(ys, names):
            g.add(Line([self.X(0), y - 0.3, 0], [self.X(9.4), y - 0.3, 0], stroke_color=GRID, stroke_width=1.2),
                  mono(n, 15).move_to([self.X(0) - 0.7, y, 0]))
        return g

    def construct(self):
        header(self, "Gang scheduling: all threads of a job run together",
               "Four threads of one parallel job meet at a barrier. Blue: job A. Amber: another job B.")
        foot = footer(self, ["Barrier  no thread continues until all four have arrived",
                             "Gang     the scheduler gives all threads of A their time slice at the same moment"])
        ys = [1.1, 0.45, -0.2, -0.85]
        names = ["core 1", "core 2", "core 3", "core 4"]
        lanes = self.lanes(ys, names)
        h = 0.42

        # 1) uncoordinated
        t1 = txt("Without co-scheduling", 22, INK, True).move_to([self.X(0), 1.75, 0], aligned_edge=LEFT)
        self.play(FadeIn(lanes), FadeIn(t1), run_time=0.5)
        a = [seg(self.X(0), self.X(5), ys[0], BLUE, h, "A"),
             seg(self.X(0), self.X(5.5), ys[1], BLUE, h, "A"),
             seg(self.X(4), self.X(8.5), ys[2], BLUE, h, "A"),
             seg(self.X(0), self.X(5), ys[3], BLUE, h, "A")]
        b = seg(self.X(0), self.X(4), ys[2], AMBER, h, "B")
        self.play(*[grow(s) for s in a[:2] + a[3:]], grow(b), run_time=1.0)
        self.play(grow(a[2]), run_time=0.7)
        waits = [seg(self.X(5), self.X(8.5), ys[0], BAD, h, "waiting", 14, opacity=0.8),
                 seg(self.X(5.5), self.X(8.5), ys[1], BAD, h, "waiting", 14, opacity=0.8),
                 seg(self.X(5), self.X(8.5), ys[3], BAD, h, "waiting", 14, opacity=0.8)]
        bar_line = DashedLine([self.X(8.5), 1.5, 0], [self.X(8.5), -1.3, 0], stroke_color=INK, stroke_width=2,
                              dash_length=0.08)
        bar_t = mono("barrier reached", 14, INK).move_to([self.X(8.5), -1.5, 0])
        self.play(*[FadeIn(w) for w in waits], Create(bar_line), FadeIn(bar_t), run_time=0.8)
        why = txt("Thread 3 was preempted by B, so three cores idle.", 20, BAD).move_to([0.0, -2.15, 0])
        self.play(FadeIn(why), run_time=0.4)
        self.wait(1.8)
        self.play(*[FadeOut(m) for m in a + waits + [b, bar_line, bar_t, why, t1]], run_time=0.5)

        # 2) gang
        t2 = txt("With gang scheduling", 22, INK, True).move_to([self.X(0), 1.75, 0], aligned_edge=LEFT)
        ga = [seg(self.X(0), self.X(5), y, BLUE, h, "A") for y in ys]
        gb = [seg(self.X(5), self.X(9), y, AMBER, h, "B") for y in ys]
        bar2 = DashedLine([self.X(5), 1.5, 0], [self.X(5), -1.3, 0], stroke_color=INK, stroke_width=2,
                          dash_length=0.08)
        bar2_t = mono("barrier reached", 14, INK).move_to([self.X(5), -1.5, 0])
        self.play(FadeIn(t2), *[grow(s) for s in ga], run_time=1.0)
        self.play(Create(bar2), FadeIn(bar2_t), run_time=0.5)
        self.play(*[grow(s) for s in gb], run_time=0.8)
        ok = txt("No idle cores at the barrier. Cost: B has to wait for its own slot.", 20, OK).move_to([0.0, -2.15, 0])
        self.play(FadeIn(ok), run_time=0.4)
        self.wait(2.0)
        self.play(*[FadeOut(m) for m in ga + gb + [bar2, bar2_t, ok, t2, lanes]], run_time=0.5)

        # 3) a sensor pipeline is something else
        self.remove(foot)
        t3 = txt("A sensor pipeline is a different problem", 24, INK, True).move_to([0, 1.45, 0])
        boxes = []
        for lab, y in [("camera preprocessing", 0.55), ("radar processing", -0.1), ("lidar processing", -0.75)]:
            r = RoundedRectangle(width=3.4, height=0.5, corner_radius=0.1, stroke_color=MUTED, stroke_width=2.5,
                                 fill_color=BG, fill_opacity=1).move_to([-3.2, y, 0])
            r.add(txt(lab, 17).move_to(r))
            boxes.append(r)
        fus = RoundedRectangle(width=2.6, height=0.9, corner_radius=0.1, stroke_color=BLUE, stroke_width=3,
                               fill_color=BG, fill_opacity=1).move_to([2.2, -0.1, 0])
        fus.add(txt("sensor fusion", 19, INK, True).move_to(fus))
        arrs = [Arrow(b.get_right(), fus.get_left() + UP * dy, buff=0.1, stroke_width=3, color=MUTED)
                for b, dy in zip(boxes, [0.25, 0.0, -0.25])]
        note = VGroup(txt("data dependency and a consistent snapshot:", 19, INK, True),
                      txt("timestamps, synchronized triggers or a static schedule.", 19, MUTED),
                      txt("Nobody needs to run at the same moment, the data just has to belong together.", 19, MUTED)
                      ).arrange(DOWN, buff=0.12).move_to([0, -2.0, 0])
        self.play(FadeIn(t3), *[FadeIn(b) for b in boxes], FadeIn(fus), run_time=0.7)
        self.play(*[GrowArrow(a_) for a_ in arrs], FadeIn(note), run_time=0.8)
        self.wait(3.0)


class SharedResourceInterference(Scene):
    """A pinned control task still slows down when an accelerator hammers the shared memory path."""

    def construct(self):
        header(self, "Placed apart is not the same as isolated",
               "A control task has its own core. The NPU has its own cluster. They still share the way to memory.")
        footer(self, ["Same core, same code, three runs. Only the neighbour's behaviour changes.",
                      "Mitigation: cache partitioning and memory bandwidth regulation, where the silicon offers them."])

        def node(label, x, y, w=2.5, color=MUTED, sw=2.5):
            r = RoundedRectangle(width=w, height=0.62, corner_radius=0.1, stroke_color=color, stroke_width=sw,
                                 fill_color=BG, fill_opacity=1).move_to([x, y, 0])
            r.add(txt(label, 17, INK).move_to(r))
            return r

        ctrl = node("control core", -5.0, 2.0, color=OK, sw=3.5)
        npu = node("NPU cluster", -5.0, 1.15, color=BLUE, sw=3.5)
        shared = node("shared cache + interconnect", -1.4, 1.575, w=3.4)
        mc = node("memory controller", 2.3, 1.575, w=2.6)
        dram = node("DRAM", 5.0, 1.575, w=1.3)
        a1 = Arrow(ctrl.get_right(), shared.get_left() + UP * 0.12, buff=0.08, stroke_width=3, color=OK)
        a2 = Arrow(npu.get_right(), shared.get_left() + DOWN * 0.12, buff=0.08, stroke_width=3, color=BLUE)
        a3 = Arrow(shared.get_right(), mc.get_left(), buff=0.08, stroke_width=3, color=MUTED)
        a4 = Arrow(mc.get_right(), dram.get_left(), buff=0.08, stroke_width=3, color=MUTED)
        self.play(*[FadeIn(m) for m in [ctrl, npu, shared, mc, dram, a1, a2, a3, a4]], run_time=0.8)

        x0, u = -2.6, 2.2          # task bar starts at x0, u units per ms
        rows = [0.2, -0.6, -1.4]
        labels = ["NPU idle", "NPU busy", "NPU busy,\nregulated"]
        lbl = VGroup(*[txt(l, 17, INK, True).move_to([-5.0, y, 0]) for l, y in zip(labels, rows)])
        lbl[2].move_to([-5.0, rows[2], 0])
        dl_x = x0 + 1.3 * u
        dline = DashedLine([dl_x, 0.55, 0], [dl_x, -1.8, 0], stroke_color=BAD, stroke_width=2.5, dash_length=0.08)
        dl_t = mono("deadline", 14, BAD).move_to([dl_x, 0.72, 0])
        self.play(FadeIn(lbl), Create(dline), FadeIn(dl_t), run_time=0.6)

        # run 1: alone
        r1 = seg(x0, x0 + 0.7 * u, rows[0], OK, 0.4, "0.7 ms")
        self.play(grow(r1), run_time=0.8)
        self.wait(0.4)

        # run 2: NPU hammers memory
        self.play(npu[0].animate.set_fill(BLUE, 0.25), a2.animate.set_stroke(BLUE, 7),
                  a3.animate.set_stroke(BAD, 6), shared[0].animate.set_stroke(BAD, 4),
                  mc[0].animate.set_stroke(BAD, 4), run_time=0.6)
        r2a = seg(x0, x0 + 0.7 * u, rows[1], OK, 0.4, "0.7 ms")
        r2b = seg(x0 + 0.7 * u, x0 + 1.6 * u, rows[1], BAD, 0.4, "waiting on memory", 14, opacity=0.85)
        self.play(grow(r2a), run_time=0.5)
        self.play(grow(r2b), run_time=0.6)
        miss = txt("deadline missed", 17, BAD, True).next_to(r2b, RIGHT, buff=0.2)
        self.play(FadeIn(miss), run_time=0.4)
        self.wait(1.0)

        # run 3: with regulation
        badge1 = txt("partitioned", 13, AMBER, True).next_to(shared, DOWN, buff=0.08)
        badge2 = txt("bandwidth cap", 13, AMBER, True).next_to(mc, DOWN, buff=0.08)
        self.play(a2.animate.set_stroke(BLUE, 3), a3.animate.set_stroke(MUTED, 3),
                  shared[0].animate.set_stroke(AMBER, 4), mc[0].animate.set_stroke(AMBER, 4),
                  FadeIn(badge1), FadeIn(badge2), run_time=0.6)
        r3a = seg(x0, x0 + 0.7 * u, rows[2], OK, 0.4, "0.7 ms")
        r3b = seg(x0 + 0.7 * u, x0 + 0.95 * u, rows[2], AMBER, 0.4)
        self.play(grow(r3a), run_time=0.5)
        self.play(grow(r3b), run_time=0.3)
        good = txt("slower than alone, but bounded", 17, OK, True)
        good.next_to(r3b, RIGHT, buff=0.2)
        if good.get_right()[0] > 6.9:
            good.scale_to_fit_width(6.9 - good.get_left()[0])
        self.play(FadeIn(good), run_time=0.4)
        self.wait(3.0)


class AcceleratorPreemption(Scene):
    """A safety job arrives while a long QM kernel runs on the accelerator."""

    X0, S = -4.7, 0.165          # x at t = 0, units per ms

    def X(self, t):
        return self.X0 + t * self.S

    def arrow(self, y):
        return Arrow([self.X(2), y + 0.55, 0], [self.X(2), y + 0.24, 0], buff=0, stroke_width=3, color=OK,
                     max_tip_length_to_length_ratio=0.45)

    def construct(self):
        header(self, "A safety job arrives on a busy accelerator",
               "Green: safety job (4 ms). Blue: QM workload. The request arrives at 2 ms, the deadline is 15 ms.")
        footer(self, ["Numbers are illustrative. Kernel launches are often not preemptible, or only at coarse points.",
                      "The wait before the safety job starts is what you have to bound, not the average."])

        ys = [1.0, -0.45, -1.9]
        titles = ["One long kernel, no preemption", "Bounded work units (5 ms slices)",
                  "Reserved slice for the safety job"]
        base = VGroup()
        for y, t in zip(ys, titles):
            base.add(Line([self.X(0), y - 0.5, 0], [self.X(52), y - 0.5, 0], stroke_color=GRID, stroke_width=1.2),
                     txt(t, 17, INK, True).move_to([self.X(0), y + 0.74, 0], aligned_edge=LEFT))
        dl = DashedLine([self.X(15), 1.95, 0], [self.X(15), -2.45, 0], stroke_color=BAD, stroke_width=2.5,
                        dash_length=0.08)
        dl_t = mono("deadline 15 ms", 14, BAD).move_to([self.X(15), 2.15, 0])
        self.play(FadeIn(base), Create(dl), FadeIn(dl_t), run_time=0.6)

        h = 0.42
        res_x = self.X(27)
        # A: one 40 ms kernel
        a_qm = seg(self.X(0), self.X(40), ys[0], BLUE, h, "QM kernel, 40 ms")
        self.play(grow(a_qm), run_time=1.0)
        a_wait = seg(self.X(2), self.X(40), ys[0] - 0.32, BAD, 0.12, opacity=0.9)
        a_safe = seg(self.X(40), self.X(44), ys[0], OK, h, "safety")
        self.play(GrowArrow(self.arrow(ys[0])), run_time=0.4)
        self.play(grow(a_wait), run_time=0.8)
        self.play(grow(a_safe), run_time=0.4)
        a_res = txt("waits 38 ms: deadline missed", 17, BAD, True).move_to([res_x, ys[0] + 0.74, 0], aligned_edge=LEFT)
        self.play(FadeIn(a_res), run_time=0.4)
        self.wait(0.8)

        # B: 5 ms slices, request served at the next boundary
        b_first = seg(self.X(0), self.X(5), ys[1], BLUE, h, "5")
        b_safe = seg(self.X(5), self.X(9), ys[1], OK, h, "safety")
        b_rest = [seg(self.X(s_), self.X(s_ + 5), ys[1], BLUE, h, None) for s_ in range(9, 44, 5)]
        self.play(grow(b_first), run_time=0.5)
        self.play(GrowArrow(self.arrow(ys[1])), run_time=0.3)
        self.play(grow(b_safe), run_time=0.4)
        self.play(*[grow(p) for p in b_rest], run_time=0.9)
        b_res = txt("waits 3 ms at most: deadline met", 17, OK, True).move_to([res_x, ys[1] + 0.74, 0], aligned_edge=LEFT)
        self.play(FadeIn(b_res), run_time=0.4)
        self.wait(0.8)

        # C: reserved slice, QM job on the rest runs longer
        c_qm = seg(self.X(0), self.X(52), ys[2], BLUE, h, "QM job on the remaining slice, 52 ms")
        c_safe = seg(self.X(2), self.X(6), ys[2] - 0.32, OK, 0.16, None)
        self.play(grow(c_qm), run_time=0.7)
        self.play(GrowArrow(self.arrow(ys[2])), run_time=0.3)
        self.play(grow(c_safe), run_time=0.4)
        c_s_t = txt("safety, own slice", 14, OK, True).next_to(c_safe, RIGHT, buff=0.1)
        c_res = txt("starts at once, QM pays in utilization", 17, OK, True).move_to([res_x - 0.3, ys[2] + 0.74, 0],
                                                                                   aligned_edge=LEFT)
        self.play(FadeIn(c_s_t), FadeIn(c_res), run_time=0.4)
        self.wait(3.0)


class BudgetModes(Scene):
    """The safety budget stays put while the dynamic part follows the driving mode."""

    MODES = [
        ("Highway driving", [25, 35, 5, 10, 5, 20]),
        ("Parking", [25, 10, 35, 15, 5, 10]),
        ("Standstill", [25, 0, 0, 20, 40, 15]),
    ]
    PARTS = [("safety functions (ASIL)", OK), ("perception", BLUE), ("surround view", AMBER),
             ("infotainment, voice", "#8b6fd1"), ("diagnostics, updates", IDLE), ("headroom", SOFT)]

    def stack(self, vals, x=-2.6, w=2.4, total_h=3.7, y0=-1.75):
        g = VGroup()
        y = y0
        for v, (_, col) in zip(vals, self.PARTS):
            hgt = max(total_h * v / 100.0, 0.001)
            r = Rectangle(width=w, height=hgt, stroke_color=BG if col != SOFT else GRID, stroke_width=1.5,
                          fill_color=col, fill_opacity=1 if col != SOFT else 0.7)
            r.move_to([x, y + hgt / 2, 0])
            g.add(r)
            y += hgt
        return g

    def construct(self):
        header(self, "Dynamic scheduling, with a fence around the safety part",
               "Share of compute capacity per domain on a central vehicle computer. Illustrative numbers.")
        footer(self, ["The safety budget is reserved at design time and identical in every mode.",
                      "Only the QM domain moves, and the mode switch itself is part of the analysis."])

        outline = Rectangle(width=2.4, height=3.7, stroke_color=MUTED, stroke_width=2.5).move_to([-2.6, 0.1, 0])
        # legend
        leg = VGroup()
        for i, (n, c) in enumerate(self.PARTS):
            sw = Square(0.22, stroke_color=GRID, stroke_width=1.5, fill_color=c,
                        fill_opacity=1 if c != SOFT else 0.7)
            t = txt(n, 18, INK)
            leg.add(VGroup(sw, t.next_to(sw, RIGHT, buff=0.15)))
        leg.arrange(DOWN, aligned_edge=LEFT, buff=0.18).move_to([3.3, 0.2, 0])
        title = txt(self.MODES[0][0], 26, INK, True).move_to([-2.6, 2.3, 0])
        cur = self.stack(self.MODES[0][1])
        self.play(FadeIn(outline), FadeIn(leg), FadeIn(title), run_time=0.6)
        self.play(*[GrowFromEdge(r, DOWN) for r in cur], run_time=1.0)
        fence = Brace(cur[0], LEFT, color=OK)
        fence_t = txt("guaranteed", 17, OK, True).next_to(fence, LEFT, buff=0.12)
        self.play(FadeIn(fence), FadeIn(fence_t), run_time=0.4)
        self.wait(1.2)

        for name, vals in self.MODES[1:]:
            new = self.stack(vals)
            new_title = txt(name, 26, INK, True).move_to([-2.6, 2.3, 0])
            self.play(*[Transform(a, b) for a, b in zip(cur, new)], Transform(title, new_title), run_time=1.4)
            self.wait(1.3)

        sw = VGroup(txt("A mode switch is a worst case too:", 18, BAD, True),
                    txt("when is a budget released,", 18, BAD),
                    txt("and from when can it be used?", 18, BAD)).arrange(DOWN, aligned_edge=LEFT, buff=0.08)
        sw.move_to([3.3, -1.95, 0])
        self.play(FadeIn(sw), run_time=0.5)
        self.wait(1.2)
        back = self.stack(self.MODES[0][1])
        back_title = txt("and back again", 26, INK, True).move_to([-2.6, 2.3, 0])
        self.play(*[Transform(a, b) for a, b in zip(cur, back)], Transform(title, back_title), run_time=1.2)
        self.wait(2.5)
