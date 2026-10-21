"""Turn drawings.json (from extract_drawings.js) into DXF sheets with a GB-style
frame, title block and (for the assembly) parts list.

Layers follow the GB/T 14665 habit: 粗实线 / 细实线 / 虚线 / 点画线 / 剖面线 / 尺寸 / 文字 / 图框.
Text uses gbenor.shx + gbcbig.shx, the stock AutoCAD Chinese drafting fonts.

Run:  python make_dxf.py   (needs ezdxf)
"""
import json
import math
import os

import ezdxf
from ezdxf.enums import TextEntityAlignment

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "dxf")
DATA = json.load(open(os.path.join(HERE, "drawings.json"), encoding="utf8"))

L_THICK, L_THIN, L_HID, L_CTR, L_HATCH, L_DIM, L_TXT, L_FRAME = (
    "01粗实线", "02细实线", "03虚线", "04点画线", "05剖面线", "06尺寸", "07文字", "08图框")
TEXT_H = {"dt": 3.5, "vl": 5, "bn": 5, "tbt": 3.5, "tbh": 5, "tbn": 7}
PARTS = [  # id, drawing no., scale
    ("body", "QF-01", 1), ("cover", "QF-02", 1), ("seal", "QF-03", 2), ("ball", "QF-04", 2),
    ("gland", "QF-07", 2), ("stem", "QF-08", 2), ("wrench", "QF-09", 1)]
SHEETS = [("A4", 210, 297, 25, 5), ("A3", 420, 297, 25, 5), ("A3竖放", 297, 420, 25, 5), ("A2", 594, 420, 25, 10), ("A1", 841, 594, 25, 10)]


def cad_text(s):
    """SHX fonts: use %%c for Ø, %%d for degree, ASCII x for multiplication."""
    return s.replace("Ø", "%%c").replace("°", "%%d").replace("×", "x")


def new_doc():
    doc = ezdxf.new("R2010", setup=True, units=ezdxf.units.MM)
    doc.header["$MEASUREMENT"] = 1
    doc.header["$LTSCALE"] = 3.5
    doc.header["$LWDISPLAY"] = 1
    doc.styles.new("GB", dxfattribs={"font": "gbenor.shx", "bigfont": "gbcbig.shx", "width": 0.7})
    for name, color, lw, lt in [(L_THICK, 7, 50, "CONTINUOUS"), (L_THIN, 3, 25, "CONTINUOUS"),
                                (L_HID, 2, 25, "DASHED"), (L_CTR, 1, 25, "CENTER"),
                                (L_HATCH, 3, 25, "CONTINUOUS"), (L_DIM, 3, 25, "CONTINUOUS"),
                                (L_TXT, 3, 25, "CONTINUOUS"), (L_FRAME, 7, 50, "CONTINUOUS")]:
        doc.layers.add(name, color=color, lineweight=lw, linetype=lt)
    ds = doc.dimstyles.new("GB")
    ds.dxf.dimtxsty = "GB"
    ds.dxf.dimtxt = 3.5
    ds.dxf.dimasz = 3
    ds.dxf.dimexe = 2
    ds.dxf.dimexo = 0
    ds.dxf.dimgap = 0.8
    ds.dxf.dimtad = 1
    ds.dxf.dimtih = 0
    ds.dxf.dimtoh = 0
    ds.dxf.dimdec = 2
    ds.dxf.dimclrd = 3
    ds.dxf.dimclre = 3
    ds.dxf.dimclrt = 3
    return doc


class Sheet:
    def __init__(self, doc, s=1.0, dx=0.0, dy=0.0):
        self.doc, self.msp, self.s, self.dx, self.dy = doc, doc.modelspace(), s, dx, dy

    def P(self, p):
        return (p[0] * self.s + self.dx, p[1] * self.s + self.dy)

    def layer(self, c):
        base = c.split()[0]
        return {"v": L_THICK, "ct": L_THICK, "t": L_THIN, "h": L_HID, "c": L_CTR, "d": L_DIM, "dot": L_DIM}.get(base, L_THIN)

    def text(self, p, s, h, align="middle", rot=0.0, layer=L_TXT):
        a = {"start": TextEntityAlignment.LEFT, "middle": TextEntityAlignment.CENTER,
             "end": TextEntityAlignment.RIGHT}[align]
        t = self.msp.add_text(cad_text(s), height=h, rotation=rot, dxfattribs={"style": "GB", "layer": layer})
        t.set_placement(p, align=a)

    def arrow(self, tip, frm):
        ux, uy = tip[0] - frm[0], tip[1] - frm[1]
        n = math.hypot(ux, uy) or 1
        ux, uy = ux / n, uy / n
        b = (tip[0] - ux * 3, tip[1] - uy * 3)
        w = 0.5
        self.msp.add_solid([tip, (b[0] - uy * w, b[1] + ux * w), (b[0] + uy * w, b[1] - ux * w)],
                           dxfattribs={"layer": L_DIM})

    def entity(self, e):
        t = e["t"]
        if t == "line":
            self.msp.add_line(self.P(e["p"][0]), self.P(e["p"][1]), dxfattribs={"layer": self.layer(e["c"])})
        elif t == "circle":
            c, r = self.P(e["p"]), e["r"] * self.s
            if e["c"] == "dot":
                h = self.msp.add_hatch(color=3, dxfattribs={"layer": L_DIM})
                h.paths.add_edge_path().add_arc(c, 0.6, 0, 360)
            else:
                self.msp.add_circle(c, r, dxfattribs={"layer": self.layer(e["c"])})
        elif t == "poly":
            pts = [(*self.P(p), p[2]) for p in e["pts"]]
            self.msp.add_lwpolyline(pts, format="xyb", close=e["closed"], dxfattribs={"layer": self.layer(e["c"])})
            cls = e["c"].split()
            fill = next((c for c in cls if c in ("s1", "s2", "s3", "sn")), None)
            if fill:
                h = self.msp.add_hatch(color=256, dxfattribs={"layer": L_HATCH})
                pat, ang, sc = {"s1": ("ANSI31", 0, 0.9), "s2": ("ANSI31", 90, 0.9),
                                "s3": ("ANSI31", 0, 0.55), "sn": ("ANSI37", 0, 0.6)}[fill]
                h.set_pattern_fill(pat, scale=sc, angle=ang)
                h.paths.add_polyline_path(pts, is_closed=True)
        elif t == "text":
            self.text(self.P(e["p"]), e["s"], TEXT_H.get(e["c"], 3.5), e["a"], e["rot"],
                      L_DIM if e["c"] == "dt" else L_TXT)
        elif t == "dim":
            p1, p2 = self.P(e["p1"]), self.P(e["p2"])
            if e["k"] == "H":
                base, ang = (p1[0], e["at"] * self.s + self.dy), 0
            else:
                base, ang = (e["at"] * self.s + self.dx, p1[1]), 90
            d = self.msp.add_linear_dim(base=base, p1=p1, p2=p2, angle=ang, text=cad_text(e["s"]),
                                        dimstyle="GB", dxfattribs={"layer": L_DIM})
            d.render()
        elif t == "dline":
            a, b = self.P(e["p"][0]), self.P(e["p"][1])
            self.msp.add_line(a, b, dxfattribs={"layer": L_DIM})
            self.arrow(b, a)
            if e["both"]:
                self.arrow(a, b)
        elif t == "leader":
            a, b = self.P(e["p"][0]), self.P(e["p"][1])
            s = e["s"]
            d = 1 if b[0] >= a[0] else -1
            w = len(s) * 3.0 + 2
            self.msp.add_line(a, b, dxfattribs={"layer": L_DIM})
            self.arrow(a, b)
            self.msp.add_line(b, (b[0] + d * w, b[1]), dxfattribs={"layer": L_DIM})
            self.text((b[0] + d * 1, b[1] + 0.8), s, 3.5, "start" if d > 0 else "end", 0, L_DIM)


def bbox(entities):
    xs, ys = [], []
    for e in entities:
        if e["t"] in ("line", "dline", "leader"):
            for p in e["p"]:
                xs.append(p[0]); ys.append(p[1])
        elif e["t"] == "circle":
            xs += [e["p"][0] - e["r"], e["p"][0] + e["r"]]; ys += [e["p"][1] - e["r"], e["p"][1] + e["r"]]
        elif e["t"] == "poly":
            for p in e["pts"]:
                xs.append(p[0]); ys.append(p[1])
        elif e["t"] == "text":
            xs.append(e["p"][0]); ys.append(e["p"][1])
        elif e["t"] == "dim":
            for p in (e["p1"], e["p2"]):
                xs.append(p[0]); ys.append(p[1])
            (ys if e["k"] == "H" else xs).append(e["at"])
    return min(xs) - 6, min(ys) - 6, max(xs) + 6, max(ys) + 6


def overlap(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def frame(sh, W, H, left, m):
    msp = sh.msp
    msp.add_lwpolyline([(0, 0), (W, 0), (W, H), (0, H)], close=True, dxfattribs={"layer": L_THIN})
    msp.add_lwpolyline([(left, m), (W - m, m), (W - m, H - m), (left, H - m)], close=True,
                       dxfattribs={"layer": L_FRAME})


def title_block(sh, x1, y0, name, material, scale, qty, dwg_no):
    """180 x 56 block in the GB/T 10609.1 arrangement, simplified for coursework."""
    msp, x0 = sh.msp, x1 - 180
    L = lambda a, b, lay=L_THIN: msp.add_line(a, b, dxfattribs={"layer": lay})
    msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y0 + 56), (x0, y0 + 56)], close=True, dxfattribs={"layer": L_FRAME})
    T = lambda x, y, s, h=3.5, a="middle": sh.text((x, y), s, h, a)
    # left: signatures (4 rows x 7 plus header rows)
    L((x0 + 50, y0), (x0 + 50, y0 + 56), L_FRAME)
    for i, lab in enumerate(["批准", "审核", "校核", "制图"]):
        yy = y0 + i * 14
        L((x0, yy + 14), (x0 + 50, yy + 14))
        T(x0 + 7, yy + 5.5, lab)
    L((x0 + 14, y0), (x0 + 14, y0 + 56)); L((x0 + 36, y0), (x0 + 36, y0 + 56))
    T(x0 + 43, y0 + 5.5 + 42, "日期", 3)
    # middle: material + school
    L((x0 + 50, y0 + 28), (x0 + 120, y0 + 28))
    T(x0 + 85, y0 + 46, material, 5)
    T(x0 + 85, y0 + 36, "材料", 3)
    T(x0 + 85, y0 + 12, "（学校  班级  学号）", 3.5)
    # right: name / scale / qty / drawing number
    L((x0 + 120, y0), (x0 + 120, y0 + 56), L_FRAME)
    L((x0 + 120, y0 + 28), (x1, y0 + 28)); L((x0 + 120, y0 + 14), (x1, y0 + 14)); L((x0 + 150, y0 + 14), (x0 + 150, y0 + 28))
    T(x0 + 150, y0 + 39, name, 7)
    T(x0 + 135, y0 + 23, "比例", 3); T(x0 + 135, y0 + 16.5, scale, 3.5)
    T(x0 + 165, y0 + 23, "数量", 3); T(x0 + 165, y0 + 16.5, str(qty), 3.5)
    T(x0 + 150, y0 + 5.5, dwg_no, 5)


def parts_list(sh, x1, y0, rows):
    """Parts list stacked on the title block: header at the bottom, items numbered upward."""
    msp, x0, rh = sh.msp, x1 - 180, 7
    cols = [0, 15, 50, 90, 105, 145, 180]
    n = len(rows) + 1
    for i in range(n + 1):
        msp.add_line((x0, y0 + i * rh), (x1, y0 + i * rh), dxfattribs={"layer": L_FRAME if i <= 1 else L_THIN})
    for k, c in enumerate(cols):
        msp.add_line((x0 + c, y0), (x0 + c, y0 + n * rh), dxfattribs={"layer": L_FRAME if k in (0, len(cols) - 1) else L_THIN})
    hdr = ["序号", "代号", "名称", "数量", "材料", "备注"]
    for k, s in enumerate(hdr):
        sh.text((x0 + (cols[k] + cols[k + 1]) / 2, y0 + 2), s, 3.5)
    for j, r in enumerate(rows):
        for k, s in enumerate(r):
            sh.text((x0 + (cols[k] + cols[k + 1]) / 2, y0 + (j + 1) * rh + 2), s, 3.5)
    return n * rh


def fit_sheet(entities, scales, extra):
    """Smallest sheet / scale / technical-requirements position that keeps the views clear of the corner blocks."""
    bx0, by0, bx1, by1 = bbox(entities)
    for scale in scales:  # keep the preferred enlargement if an A4/A3 sheet can hold it, else fall back to 1:1
        for size, W, H, left, m in (SHEETS[:3] if scale > 1 else SHEETS):
            w, h = (bx1 - bx0) * scale, (by1 - by0) * scale
            il, ib, ir, it = left, m, W - m, H - m
            ox, oy = il + 12, it - 10 - h
            cont = (ox, oy, ox + w, oy + h)
            top = ib + 56 + extra["rows"] * 7
            for tech in (["beside"] if extra["rows"] else ["left", "beside", "above"]):
                blocked = [(ir - 180, ib, ir, top)]
                if tech == "beside":
                    if ir - 180 - 158 < il:
                        continue
                    blocked.append((ir - 180 - 158, ib, ir - 180, ib + 40))
                elif tech == "left":
                    if il + 140 > ir - 185:
                        continue
                    blocked.append((il, ib, il + 140, ib + 40))
                else:  # narrow sheet: stack the requirements on top of the title block
                    blocked.append((ir - 180, top, ir, top + 36))
                if ox + w <= ir - 5 and oy >= ib + 5 and not any(overlap(cont, r) for r in blocked):
                    # centre the views in the free space: above the corner blocks if they fit there, else the whole sheet
                    top_of_blocks = max(r[3] for r in blocked)
                    for y_lo in (top_of_blocks + 8, ib + 5):
                        cx, cy = (il + ir) / 2 - w / 2, (y_lo + it) / 2 - h / 2
                        c2 = (cx, cy, cx + w, cy + h)
                        if cy >= y_lo - 1e-6 and cx >= il + 5 and not any(overlap(c2, r) for r in blocked):
                            ox, oy = cx, cy
                            break
                    return size, W, H, left, m, scale, tech, (ox - bx0 * scale, oy - by0 * scale), (w, h)
    raise RuntimeError("views do not fit any sheet")


def build(name, entities, scales, title, extra):
    size, W, H, left, m, scale, tech, (dx, dy), (w, h) = fit_sheet(entities, scales, extra)
    il, ib, ir = left, m, W - m
    doc = new_doc()
    sh = Sheet(doc, scale, dx, dy)
    for e in entities:
        sh.entity(e)
    page = Sheet(doc)
    frame(page, W, H, left, m)
    t = list(title)
    t[2] = f"{scale}:1" if scale >= 1 else f"1:{round(1 / scale)}"
    title_block(page, ir, ib, *t)
    if extra["rows"]:
        parts_list(page, ir, ib + 56, extra["table"])
    x = {"left": il + 10, "beside": ir - 180 - 150, "above": ir - 176}[tech]
    y = ib + 34 if tech != "above" else ib + 56 + extra["rows"] * 7 + 30
    page.text((x, y), "技术要求", 5, "start")
    for i, r in enumerate(extra["req"]):
        page.text((x, y - 8 - i * 7), f"{i + 1}. {r}", 3.5, "start")
    os.makedirs(OUT, exist_ok=True)
    fn = os.path.join(OUT, name + ".dxf")
    doc.saveas(fn)
    print(f"{name:24s} {size:6s} scale {t[2]:4s} views {w:.0f}x{h:.0f} mm")
    return {"file": os.path.basename(fn), "size": size, "scale": t[2]}


def main():
    meta, info = DATA["meta"], DATA["info"]
    sheets = {}
    for pid, no, sc in PARTS:
        m = meta[pid]
        scales = [sc, 1] if sc > 1 else [1]
        sheets[pid] = build(f"{no}_{m['name']}", DATA["drawings"][pid], scales,
                            (m["name"], m["mat"], "", m["qty"], no), {"rows": 0, "req": info[pid]["req"]})
    rows = [["1", "QF-01", "阀体", "1", "ZG230-450", ""], ["2", "QF-02", "阀盖", "1", "ZG230-450", ""],
            ["3", "QF-03", "密封圈", "2", "聚四氟乙烯", ""], ["4", "QF-04", "阀芯", "1", "40Cr", ""],
            ["5", "GB/T 5783", "螺栓 M8x25", "4", "Q235", "性能等级 4.8"], ["6", "QF-06", "填料", "1", "聚四氟乙烯", ""],
            ["7", "QF-07", "填料压紧套", "1", "35", ""], ["8", "QF-08", "阀杆", "1", "40Cr", ""],
            ["9", "QF-09", "扳手", "1", "ZG230-450", ""]]
    sheets["assembly"] = build("QF-00_球阀装配图", DATA["drawings"]["assembly"], [1], ("球阀", "", "", 1, "QF-00"),
                               {"rows": len(rows) + 1, "table": rows,
                                "req": ["装配后扳手转动灵活，开、关各 90° 到位。", "以 1.6 MPa 水压做密封试验，不得渗漏。",
                                        "两法兰之间保留约 1.6 间隙，不得强行压平。"]})


if __name__ == "__main__":
    main()
