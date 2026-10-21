"""Build the ball valve solids with CadQuery (OpenCascade) and export STEP files.

All parts are modelled in the assembly frame used by the web page and the
drawings: origin at the ball centre, +X along the flow towards the outlet
(the cover sits on -X), +Y up the stem axis, units in mm. SolidWorks uses the
same "Y up" convention, so each part's origin lands on the assembly origin.

The bolt is the only part modelled in its own frame (axis +X, head underside
at X=0) because it is inserted four times.

Run:  python build_models.py   (needs cadquery)
"""
import math
import os

import cadquery as cq

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "step")
V = cq.Vector


def revolve_x(pts):
    """Closed (x, r) profile in the XY plane revolved about the X axis."""
    wp = cq.Workplane("XY").polyline(pts).close()
    return wp.revolve(360, (0, 0, 0), (1, 0, 0))


def revolve_y(pts):
    """Closed (r, y) profile in the XY plane revolved about the Y axis."""
    wp = cq.Workplane("XY").polyline(pts).close()
    return wp.revolve(360, (0, 0, 0), (0, 1, 0))


def cyl_y(r, y0, y1):
    return cq.Workplane("XZ", origin=(0, y0, 0)).circle(r).extrude(-(y1 - y0))


def cyl_x(r, x0, x1, y=0.0, z=0.0):
    return cq.Workplane("YZ", origin=(x0, y, z)).circle(r).extrude(x1 - x0)


def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def prism_xz(points_xz, y0, h):
    """Polygon given in world (x, z) at height y0, extruded +h along Y."""
    wire = cq.Wire.makePolygon([V(x, y0, z) for x, z in points_xz], close=True)
    face = cq.Face.makeFromWires(wire)
    return cq.Workplane().add(cq.Solid.extrudeLinear(face, V(0, h, 0)))


def sector_xz(r1, r2, a1, a2, y0, h, n=48):
    """Ring sector between radii r1..r2 and angles a1..a2 (deg, measured from +X toward +Z)."""
    A = [math.radians(a1 + (a2 - a1) * i / n) for i in range(n + 1)]
    outer = [(r2 * math.cos(a), r2 * math.sin(a)) for a in A]
    inner = [(r1 * math.cos(a), r1 * math.sin(a)) for a in reversed(A)] if r1 > 0 else [(0.0, 0.0)]
    return prism_xz(outer + inner, y0, h)


def flange(x0, depth, hole_d, rc=6.0):
    f = box(x0, x0 + depth, -38.75, 38.75, -38.75, 38.75).edges("|X").fillet(rc)
    for y, z in [(26.5, 26.5), (-26.5, 26.5), (26.5, -26.5), (-26.5, -26.5)]:
        f = f.cut(cyl_x(hole_d / 2, x0 - 1, x0 + depth + 1, y, z))
    return f


# ---------------------------------------------------------------- 1 阀体 body
def body():
    outer = (cq.Workplane("XY").moveTo(-21.5, 0).lineTo(-21.5, 28).lineTo(8, 28)
             .spline([(16, 26.4), (24, 22.5), (31, 21)], includeCurrent=True,
                     tangents=[(1, 0), (1, 0)])
             .lineTo(40.6, 21).lineTo(41.5, 20.1).lineTo(41.5, 17.5).lineTo(43.5, 17.5)
             .lineTo(43.5, 19).lineTo(58, 19).lineTo(59, 18).lineTo(59, 0).close()
             .revolve(360, (0, 0, 0), (1, 0, 0)))
    b = flange(-26, 14, 8.0).union(outer)
    b = b.union(cyl_y(18, 12, 61.25))
    b = b.union(sector_xz(12, 18, 137, 223, 61.2, 4.05))            # 90° limit block, flange side
    b = b.cut(revolve_x([(-26.5, 0), (-26.5, 25), (-21, 25), (-21, 22), (15.76, 22), (15.76, 17.5),
                         (22.76, 17.5), (22.76, 10), (57, 10), (57, 14), (59.5, 14), (59.5, 0)]))
    b = b.cut(revolve_y([(0, 12), (9, 12), (9, 30), (7, 30), (7, 37.85), (10.75, 37.85),
                         (10.75, 44), (12, 44), (12, 66), (0, 66)]))
    try:
        b = b.edges(cq.selectors.BoxSelector((40, -22, -22), (60, 22, 22))).edges("%CIRCLE").chamfer(0.4)
    except Exception:
        pass
    return b


# ---------------------------------------------------------------- 2 阀盖 cover
def cover():
    outer = (cq.Workplane("XY").moveTo(-67.46, 0).lineTo(-67.46, 18).lineTo(-66.46, 19)
             .lineTo(-51.96, 19).lineTo(-51.96, 17.5).lineTo(-47, 17.5)
             .spline([(-43.5, 18.8), (-40.1, 22.2)], includeCurrent=True, tangents=[(1, 0), (0.5, 1)])
             .lineTo(-40.1, 30).lineTo(-27.6, 30).lineTo(-27.6, 26.18).lineTo(-26, 26.18)
             .lineTo(-26, 24.9).lineTo(-21.1, 24.9).lineTo(-21.1, 21).lineTo(-15.76, 21)
             .lineTo(-15.76, 0).close()
             .revolve(360, (0, 0, 0), (1, 0, 0)))
    c = flange(-40.1, 12.5, 9.0).union(outer)
    c = c.cut(revolve_x([(-68, 0), (-68, 14), (-65.46, 14), (-65.46, 10), (-22.76, 10),
                         (-22.76, 17.5), (-15.5, 17.5), (-15.5, 0)]))
    return c


# ---------------------------------------------------------------- 3 密封圈 seal (left position)
def seal():
    ring = cyl_x(17.5, -22.76, -14.76).cut(cyl_x(10, -23, -14))
    return ring.cut(cq.Workplane().add(cq.Solid.makeSphere(20.5, angleDegrees1=-90, angleDegrees2=90)))


# ---------------------------------------------------------------- 4 阀芯 ball
def ball():
    s = cq.Workplane().add(cq.Solid.makeSphere(20.5, angleDegrees1=-90, angleDegrees2=90))
    s = s.intersect(box(-15.9, 15.9, -25, 25, -25, 25))
    s = s.cut(cyl_x(10, -20, 20))
    s = s.cut(box(-4.5, 4.5, 13.5, 25, -25, 25))       # slot across the top, perpendicular to the bore
    return s


# ---------------------------------------------------------------- 6 填料 packing
def packing():
    return revolve_y([(7, 37.85), (10.65, 37.85), (10.65, 45.85), (7, 45.85)])


# ---------------------------------------------------------------- 7 填料压紧套 gland
def gland():
    g = revolve_y([(7.21, 45.85), (11.9, 45.85), (11.9, 57.25), (10.75, 57.25), (10.75, 61.25),
                   (8, 61.25), (8, 57.25), (7.21, 57.25)])
    g = g.cut(box(-1.5, 1.5, 58.25, 62, -13, 13))      # two screwdriver slots on the top band
    return g


# ---------------------------------------------------------------- 8 阀杆 stem
def stem():
    s = cyl_y(9, 20, 30).union(cyl_y(7, 29.9, 57.4))
    sq = box(-5.25, 5.25, 57.3, 75.3, -5.25, 5.25).faces(">Y").edges().chamfer(1.0)
    s = s.union(sq)
    tenon = cyl_y(9, 14, 20.1).intersect(box(-4.1, 4.1, 13, 21, -10, 10))
    return s.union(tenon)


# ---------------------------------------------------------------- 9 扳手 wrench (open position, handle along +X)
def wrench():
    w = lambda u: 13 - 5.48 * (u - 10.48) / 145.95
    head = cyl_y(16.7, 65.47, 75.97)
    lug = sector_xz(0, 16.7, -135, 45, 61.25, 4.3)                 # half-ring stop lug underneath
    elev = (cq.Workplane("XY").polyline([(8, 67.57), (16.7, 67.57), (52.95, 84.47), (163.95, 84.47),
                                         (163.95, 92.87), (52.95, 92.87), (16.7, 75.97), (8, 75.97)])
            .close().extrude(40).translate((0, 0, -20)))
    e1 = cq.Edge.makeLine(V(8, 60, w(8)), V(156.43, 60, w(156.43)))
    e2 = cq.Edge.makeThreePointArc(V(156.43, 60, 7.52), V(163.95, 60, 0), V(156.43, 60, -7.52))
    e3 = cq.Edge.makeLine(V(156.43, 60, -7.52), V(8, 60, -w(8)))
    e4 = cq.Edge.makeLine(V(8, 60, -w(8)), V(8, 60, w(8)))
    plan = cq.Workplane().add(cq.Solid.extrudeLinear(cq.Face.makeFromWires(cq.Wire.assembleEdges([e1, e2, e3, e4])), V(0, 40, 0)))
    handle = elev.intersect(plan)
    wr = head.union(lug).union(handle)
    wr = wr.cut(box(-5.5, 5.5, 60, 80, -5.5, 5.5))
    return wr


# ---------------------------------------------------------------- 5 螺栓 bolt M8x25 (own frame)
def bolt():
    hexagon = cq.Workplane("YZ", origin=(-5.3, 0, 0)).polygon(6, 15.01).extrude(5.3)
    hexagon = hexagon.edges(">X or <X").chamfer(0.5)
    shank = cyl_x(3.95, -0.2, 25).faces(">X").edges().chamfer(0.8)
    return hexagon.union(shank)


PARTS = [
    # file, Chinese name, builder, colour (r, g, b)
    ("QF-01_Body", "阀体", body, (0.18, 0.47, 0.80)),
    ("QF-02_Cover", "阀盖", cover, (0.80, 0.82, 0.84)),
    ("QF-03_Seal", "密封圈", seal, (0.95, 0.94, 0.90)),
    ("QF-04_Ball", "阀芯", ball, (0.86, 0.87, 0.89)),
    ("QF-05_Bolt_M8x25", "螺栓", bolt, (0.70, 0.72, 0.75)),
    ("QF-06_Packing", "填料", packing, (0.36, 0.38, 0.40)),
    ("QF-07_Gland", "填料压紧套", gland, (0.80, 0.82, 0.84)),
    ("QF-08_Stem", "阀杆", stem, (0.86, 0.87, 0.89)),
    ("QF-09_Wrench", "扳手", wrench, (0.18, 0.47, 0.80)),
]

BOLT_POS = [(26.5, 26.5), (-26.5, 26.5), (26.5, -26.5), (-26.5, -26.5)]


def main():
    os.makedirs(OUT, exist_ok=True)
    shapes = {}
    for fname, cname, fn, rgb in PARTS:
        wp = fn()
        solid = wp.val() if len(wp.vals()) == 1 else wp.combine().val()
        assert solid.isValid(), fname
        shapes[fname] = solid
        cq.exporters.export(cq.Workplane().add(solid), os.path.join(OUT, fname + ".step"))
        print(f"{fname:20s} {cname:6s} volume={solid.Volume():10.1f} mm3  valid={solid.isValid()}")

    asm = cq.Assembly(name="Ball_Valve")
    col = {f: cq.Color(*rgb) for f, _, _, rgb in PARTS}
    for f in ["QF-01_Body", "QF-02_Cover", "QF-04_Ball", "QF-06_Packing", "QF-07_Gland", "QF-08_Stem", "QF-09_Wrench"]:
        asm.add(shapes[f], name=f, color=col[f])
    asm.add(shapes["QF-03_Seal"], name="QF-03_Seal-1", color=col["QF-03_Seal"])
    asm.add(shapes["QF-03_Seal"], name="QF-03_Seal-2", color=cq.Color(0.90, 0.87, 0.63),
            loc=cq.Location(V(0, 0, 0), V(0, 1, 0), 180))
    for i, (y, z) in enumerate(BOLT_POS, 1):
        asm.add(shapes["QF-05_Bolt_M8x25"], name=f"QF-05_Bolt-{i}", color=col["QF-05_Bolt_M8x25"],
                loc=cq.Location(V(-40.15, y, z)))
    asm.save(os.path.join(OUT, "QF-00_Ball_Valve_Assembly.step"))

    # interference check between neighbouring parts in the assembled position
    placed = {k: v for k, v in shapes.items() if k not in ("QF-03_Seal", "QF-05_Bolt_M8x25")}
    placed["Seal-L"] = shapes["QF-03_Seal"]
    placed["Seal-R"] = shapes["QF-03_Seal"].rotate(V(0, 0, 0), V(0, 1, 0), 180)
    for i, (y, z) in enumerate(BOLT_POS, 1):
        placed[f"Bolt-{i}"] = shapes["QF-05_Bolt_M8x25"].translate(V(-40.15, y, z))
    names = list(placed)
    worst = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = placed[names[i]], placed[names[j]]
            inter = a.intersect(b)
            vol = inter.Volume() if inter.isValid() else 0
            if vol > 1e-3:
                worst.append((vol, names[i], names[j]))
    print("interference:", sorted(worst, reverse=True) or "none")


if __name__ == "__main__":
    main()
