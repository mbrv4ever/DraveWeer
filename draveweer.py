# -*- coding: utf-8 -*-
"""DraveWeer - een mooie weer-app (PyQt6) met grafische metertjes.

- Huidig weer met metertjes (temperatuur, wind, luchtvochtigheid) en een
  getekend weericoon.
- Uurverwachting (24u) als grafiek.
- 7-daagse verwachting als kaartjes.
- Plaats zoeken + favorieten opslaan; onthoudt je laatste plaats.

Gegevens: Open-Meteo (gratis, geen sleutel). Zie weer_engine.py.
"""
import datetime
import json
import math
import os
import random
import sys

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRectF, QPointF, QTimer
from PyQt6.QtGui import (QColor, QPainter, QPen, QBrush, QFont, QPolygonF,
                         QLinearGradient, QPainterPath, QIcon, QAction, QPixmap)
from PyQt6.QtWidgets import (QApplication, QWidget, QLabel, QLineEdit, QPushButton,
                             QComboBox, QHBoxLayout, QVBoxLayout, QFrame,
                             QSizePolicy, QSystemTrayIcon, QMenu)

import weer_engine as we


def _base():
    """Map waar de app draait (werkt ook als .exe)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _res(*parts):
    """Pad naar een meegebakken bestand (assets), ook in de .exe."""
    base = getattr(sys, "_MEIPASS", None) or _base()
    return os.path.join(base, *parts)


CFG = os.path.join(_base(), "draveweer_cfg.json")

BG = "#0c1016"
PANEL = "#161c26"
TEXT = "#e8edf6"
SUB = "#9fb0c7"
ACCENT = "#5aa6e0"

ICON_KLEUR = {
    "zon": "#f6c945", "halfbewolkt": "#cfd6e0", "bewolkt": "#aeb8c6",
    "mist": "#b9c0cb", "motregen": "#7fb6e6", "regen": "#5aa6e0",
    "buien": "#6fb0e2", "sneeuw": "#dce7f5", "onweer": "#c9a6f0",
}

KOMPAS = ["N", "NO", "O", "ZO", "Z", "ZW", "W", "NW"]


def kompas(graden):
    if graden is None:
        return ""
    return KOMPAS[int((graden % 360) / 45.0 + 0.5) % 8]


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------
def load_cfg():
    try:
        with open(CFG, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"favorieten": [], "laatste": None}


def save_cfg(cfg):
    try:
        with open(CFG, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# weericoon tekenen
# ---------------------------------------------------------------------------
def teken_weericoon(p, cx, cy, s, cat, dag=True):
    """Teken een weericoon (cat = categorie uit de motor) rond (cx,cy), maat s."""
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    geel = QColor("#f6c945")
    wolk = QColor("#cdd6e2")
    wolkd = QColor("#aeb8c6")
    drup = QColor("#5aa6e0")

    def zon(x, y, r):
        p.setPen(QPen(geel, max(2.0, s * 0.05)))
        for i in range(8):
            a = i * math.pi / 4
            p.drawLine(QPointF(x + math.cos(a) * r * 1.35, y + math.sin(a) * r * 1.35),
                       QPointF(x + math.cos(a) * r * 1.75, y + math.sin(a) * r * 1.75))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(geel)
        p.drawEllipse(QPointF(x, y), r, r)

    def maan(x, y, r):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#e6ecf7"))
        p.drawEllipse(QPointF(x, y), r, r)
        p.setBrush(QColor(BG))
        p.drawEllipse(QPointF(x + r * 0.45, y - r * 0.25), r * 0.9, r * 0.9)

    def wolkje(x, y, w, kleur):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(kleur)
        h = w * 0.62
        p.drawEllipse(QPointF(x - w * 0.22, y), h * 0.55, h * 0.55)
        p.drawEllipse(QPointF(x + w * 0.05, y - h * 0.18), h * 0.66, h * 0.66)
        p.drawEllipse(QPointF(x + w * 0.30, y), h * 0.5, h * 0.5)
        p.drawRoundedRect(QRectF(x - w * 0.40, y, w * 0.82, h * 0.5), h * 0.25, h * 0.25)

    def druppels(x, y, n, kleur):
        p.setPen(QPen(kleur, max(2.0, s * 0.06)))
        for i in range(n):
            dx = x + (i - (n - 1) / 2.0) * s * 0.18
            p.drawLine(QPointF(dx, y), QPointF(dx - s * 0.05, y + s * 0.18))

    if cat == "zon":
        (zon if dag else maan)(cx, cy, s * 0.34)
    elif cat == "halfbewolkt":
        (zon if dag else maan)(cx - s * 0.18, cy - s * 0.16, s * 0.24)
        wolkje(cx + s * 0.08, cy + s * 0.05, s * 0.7, wolk)
    elif cat == "bewolkt":
        wolkje(cx - s * 0.1, cy - s * 0.08, s * 0.62, wolkd)
        wolkje(cx + s * 0.06, cy + s * 0.08, s * 0.72, wolk)
    elif cat == "mist":
        wolkje(cx, cy - s * 0.1, s * 0.7, wolk)
        p.setPen(QPen(wolkd, max(2.0, s * 0.05)))
        for i in range(3):
            yy = cy + s * 0.18 + i * s * 0.12
            p.drawLine(QPointF(cx - s * 0.35, yy), QPointF(cx + s * 0.35, yy))
    elif cat in ("motregen", "regen"):
        wolkje(cx, cy - s * 0.12, s * 0.72, wolkd)
        druppels(cx, cy + s * 0.2, 3 if cat == "motregen" else 4, drup)
    elif cat == "buien":
        (zon if dag else maan)(cx - s * 0.22, cy - s * 0.22, s * 0.2)
        wolkje(cx + s * 0.05, cy - s * 0.05, s * 0.7, wolkd)
        druppels(cx + s * 0.05, cy + s * 0.22, 3, drup)
    elif cat == "sneeuw":
        wolkje(cx, cy - s * 0.12, s * 0.72, wolk)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#eaf1fb"))
        for i in range(4):
            dx = cx + (i - 1.5) * s * 0.18
            p.drawEllipse(QPointF(dx, cy + s * 0.24), s * 0.045, s * 0.045)
    elif cat == "onweer":
        wolkje(cx, cy - s * 0.12, s * 0.72, wolkd)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#f6c945"))
        bolt = QPolygonF([QPointF(cx - s * 0.02, cy + s * 0.05),
                          QPointF(cx + s * 0.14, cy + s * 0.05),
                          QPointF(cx + s * 0.02, cy + s * 0.22),
                          QPointF(cx + s * 0.10, cy + s * 0.22),
                          QPointF(cx - s * 0.10, cy + s * 0.46),
                          QPointF(cx - s * 0.02, cy + s * 0.24),
                          QPointF(cx - s * 0.12, cy + s * 0.24)])
        p.drawPolygon(bolt)
    else:
        wolkje(cx, cy, s * 0.7, wolk)


# ---------------------------------------------------------------------------
# metertje (cirkelvormige gauge)
# ---------------------------------------------------------------------------
class Meter(QWidget):
    def __init__(self, label, unit, vmin, vmax, kleur):
        super().__init__()
        self.label = label
        self.unit = unit
        self.vmin = vmin
        self.vmax = vmax
        self.kleur = QColor(kleur)
        self.value = None
        self.setMinimumSize(150, 150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_value(self, v):
        self.value = v
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        side = min(w, h)
        m = side * 0.14
        rect = QRectF((w - side) / 2 + m, (h - side) / 2 + m, side - 2 * m, side - 2 * m)
        start = 225 * 16
        span = -270 * 16
        # achtergrondboog
        p.setPen(QPen(QColor("#26303d"), side * 0.08, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap))
        p.drawArc(rect, start, span)
        # waardeboog
        if self.value is not None:
            frac = (self.value - self.vmin) / float(self.vmax - self.vmin or 1)
            frac = max(0.0, min(1.0, frac))
            p.setPen(QPen(self.kleur, side * 0.08, Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            p.drawArc(rect, start, int(span * frac))
        # waarde-tekst
        p.setPen(QColor(TEXT))
        f = QFont("Segoe UI", int(side * 0.17), QFont.Weight.Bold)
        p.setFont(f)
        txt = "--" if self.value is None else ("%d" % round(self.value))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, txt + self.unit)
        # label
        p.setPen(QColor(SUB))
        p.setFont(QFont("Segoe UI", int(side * 0.085)))
        lr = QRectF(rect.x(), rect.bottom() - side * 0.02, rect.width(), side * 0.16)
        p.drawText(lr, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                   self.label)


# ---------------------------------------------------------------------------
# uurgrafiek
# ---------------------------------------------------------------------------
class UurGrafiek(QWidget):
    def __init__(self):
        super().__init__()
        self.uur = []
        self.setMinimumHeight(170)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_uur(self, uur):
        self.uur = uur or []
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        if not self.uur:
            return
        pad_l, pad_r, pad_t, pad_b = 16, 16, 22, 34
        cw = w - pad_l - pad_r
        ch = h - pad_t - pad_b
        temps = [u["temp"] for u in self.uur if u["temp"] is not None]
        if not temps:
            return
        tmin, tmax = min(temps), max(temps)
        if tmax - tmin < 1:
            tmax = tmin + 1
        n = len(self.uur)

        def xy(i, t):
            x = pad_l + cw * (i / float(max(1, n - 1)))
            y = pad_t + ch * (1 - (t - tmin) / float(tmax - tmin))
            return QPointF(x, y)

        # regenkans als lichte balkjes
        for i, u in enumerate(self.uur):
            rk = u.get("regen")
            if rk:
                bx = pad_l + cw * (i / float(max(1, n - 1)))
                bh = ch * (rk / 100.0)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(90, 166, 224, 60))
                p.drawRect(QRectF(bx - cw / n * 0.3, pad_t + ch - bh,
                                  cw / n * 0.6, bh))

        # temperatuurlijn met verloop eronder
        path = QPainterPath()
        for i, u in enumerate(self.uur):
            if u["temp"] is None:
                continue
            pt = xy(i, u["temp"])
            if path.elementCount() == 0:
                path.moveTo(pt)
            else:
                path.lineTo(pt)
        grad = QLinearGradient(0, pad_t, 0, pad_t + ch)
        grad.setColorAt(0, QColor(246, 201, 69, 120))
        grad.setColorAt(1, QColor(246, 201, 69, 0))
        fill = QPainterPath(path)
        fill.lineTo(xy(n - 1, tmin))
        fill.lineTo(xy(0, tmin))
        fill.closeSubpath()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawPath(fill)
        p.setPen(QPen(QColor("#f6c945"), 2.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

        # labels (elke 3 uur) + temperatuur erboven
        p.setFont(QFont("Segoe UI", 9))
        for i, u in enumerate(self.uur):
            if i % 3 != 0:
                continue
            x = pad_l + cw * (i / float(max(1, n - 1)))
            p.setPen(QColor(SUB))
            p.drawText(QRectF(x - 20, h - pad_b + 6, 40, 16),
                       Qt.AlignmentFlag.AlignCenter, u["tijd"])
            if u["temp"] is not None:
                p.setPen(QColor(TEXT))
                pt = xy(i, u["temp"])
                p.drawText(QRectF(pt.x() - 20, pt.y() - 20, 40, 16),
                           Qt.AlignmentFlag.AlignCenter, "%d" % round(u["temp"]))


# ---------------------------------------------------------------------------
# dag-kaartje (7-daagse)
# ---------------------------------------------------------------------------
class DagKaart(QFrame):
    def __init__(self):
        super().__init__()
        self.dag = None
        self.setMinimumSize(86, 150)
        self.setStyleSheet("background:%s; border-radius:12px;" % PANEL)

    def set_dag(self, d):
        self.dag = d
        self.update()

    def paintEvent(self, e):
        super().paintEvent(e)
        if not self.dag:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w = self.width()
        d = self.dag
        p.setPen(QColor(TEXT))
        p.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        p.drawText(QRectF(0, 8, w, 22), Qt.AlignmentFlag.AlignCenter, d["dag"])
        teken_weericoon(p, w / 2, 62, 42, d["icoon"], True)
        p.setPen(QColor(TEXT))
        p.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        mx = "--" if d["max"] is None else "%d" % round(d["max"])
        p.drawText(QRectF(0, 96, w, 22), Qt.AlignmentFlag.AlignCenter, mx + "°")
        p.setPen(QColor(SUB))
        p.setFont(QFont("Segoe UI", 11))
        mn = "--" if d["min"] is None else "%d" % round(d["min"])
        p.drawText(QRectF(0, 118, w, 20), Qt.AlignmentFlag.AlignCenter, mn + "°")
        if d.get("regen"):
            p.setPen(QColor(ACCENT))
            p.setFont(QFont("Segoe UI", 10))
            p.drawText(QRectF(0, 136, w, 16), Qt.AlignmentFlag.AlignCenter,
                       "%d%%" % d["regen"])


# huidig-weericoon als los widget MET animatie (regen/sneeuw/bliksem)
class GrootIcoon(QWidget):
    def __init__(self):
        super().__init__()
        self.cat = "bewolkt"
        self.dag = True
        self.setMinimumSize(150, 150)
        self._parts = []
        self._flash = 0.0
        self._t = QTimer(self)
        self._t.timeout.connect(self._stap)
        self._t.start(45)

    def set(self, cat, dag):
        self.cat = cat
        self.dag = dag
        self._parts = []
        self.update()

    def _mode(self):
        if self.cat in ("regen", "motregen", "buien", "onweer"):
            return "regen"
        if self.cat == "sneeuw":
            return "sneeuw"
        return ""

    def _stap(self):
        m = self._mode()
        w, h = self.width(), self.height()
        if m:
            maxn = 40 if m == "regen" else 24
            for _ in range(2 if m == "regen" else 1):
                if len(self._parts) < maxn:
                    self._parts.append([random.uniform(0.18, 0.82) * w,
                                        random.uniform(0.46, 0.6) * h,
                                        random.uniform(0.5, 1.0)])
            sp = (h * 0.05) if m == "regen" else (h * 0.012)
            for pt in self._parts:
                pt[1] += sp * (0.6 + pt[2])
                if m == "sneeuw":
                    pt[0] += math.sin(pt[1] * 0.06) * 0.7
            self._parts = [pt for pt in self._parts if pt[1] < h * 0.95]
        else:
            self._parts = []
        if self.cat == "onweer":
            if self._flash > 0:
                self._flash = max(0.0, self._flash - 0.12)
            elif random.random() < 0.025:
                self._flash = 1.0
        else:
            self._flash = 0.0
        if m or self._flash > 0:
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        s = min(self.width(), self.height())
        teken_weericoon(p, self.width() / 2, self.height() / 2, s * 0.8,
                        self.cat, self.dag)
        m = self._mode()
        if m == "regen":
            p.setPen(QPen(QColor(120, 180, 235, 190), max(1.5, s * 0.018)))
            for x, y, sp in self._parts:
                p.drawLine(QPointF(x, y), QPointF(x - s * 0.03, y + s * 0.10))
        elif m == "sneeuw":
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(234, 241, 251, 220))
            for x, y, sp in self._parts:
                p.drawEllipse(QPointF(x, y), s * 0.02, s * 0.02)
        if self._flash > 0:
            p.fillRect(self.rect(), QColor(255, 246, 200, int(110 * self._flash)))


# windwijzer: kompas met pijl (richting) + snelheid in het midden
class WindWijzer(QWidget):
    def __init__(self):
        super().__init__()
        self.speed = None
        self.deg = None
        self.setMinimumSize(140, 140)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_wind(self, speed, deg):
        self.speed = speed
        self.deg = deg
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        side = min(w, h)
        cx, cy = w / 2, h / 2
        R = side * 0.38
        p.setPen(QPen(QColor("#26303d"), side * 0.045))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), R, R)
        p.setFont(QFont("Segoe UI", int(side * 0.085), QFont.Weight.Bold))
        p.setPen(QColor(SUB))
        for lbl, ang in (("N", -90), ("O", 0), ("Z", 90), ("W", 180)):
            a = math.radians(ang)
            lx = cx + math.cos(a) * R * 0.84
            ly = cy + math.sin(a) * R * 0.84
            p.drawText(QRectF(lx - 12, ly - 11, 24, 22),
                       Qt.AlignmentFlag.AlignCenter, lbl)
        if self.deg is not None:
            a = math.radians(self.deg - 90)            # bron-richting op scherm
            src = QPointF(cx + math.cos(a) * R * 0.72, cy + math.sin(a) * R * 0.72)
            dwx, dwy = -math.cos(a), -math.sin(a)      # waar de wind heen waait
            head = QPointF(cx + dwx * R * 0.30, cy + dwy * R * 0.30)
            p.setPen(QPen(QColor(ACCENT), side * 0.04, Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            p.drawLine(src, head)
            px, py = -dwy, dwx
            ah = side * 0.07
            tip = QPointF(head.x() + dwx * ah, head.y() + dwy * ah)
            l = QPointF(head.x() + px * ah * 0.6, head.y() + py * ah * 0.6)
            r = QPointF(head.x() - px * ah * 0.6, head.y() - py * ah * 0.6)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(ACCENT))
            p.drawPolygon(QPolygonF([tip, l, r]))
        p.setPen(QColor(TEXT))
        p.setFont(QFont("Segoe UI", int(side * 0.15), QFont.Weight.Bold))
        txt = "--" if self.speed is None else "%d" % round(self.speed)
        p.drawText(QRectF(cx - R, cy - R * 0.55, 2 * R, R * 0.7),
                   Qt.AlignmentFlag.AlignCenter, txt)
        p.setPen(QColor(SUB))
        p.setFont(QFont("Segoe UI", int(side * 0.072)))
        sub = "km/u" + (("  " + kompas(self.deg)) if self.deg is not None else "")
        p.drawText(QRectF(cx - R, cy + R * 0.12, 2 * R, R * 0.5),
                   Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, sub)


# ---------------------------------------------------------------------------
# achtergrond-threads (zodat de app niet vastloopt)
# ---------------------------------------------------------------------------
class ZoekThread(QThread):
    klaar = pyqtSignal(object)

    def __init__(self, naam):
        super().__init__()
        self.naam = naam

    def run(self):
        self.klaar.emit(we.zoek_plaats(self.naam))


class WeerThread(QThread):
    klaar = pyqtSignal(object)

    def __init__(self, lat, lon):
        super().__init__()
        self.lat, self.lon = lat, lon

    def run(self):
        self.klaar.emit(we.haal_weer(self.lat, self.lon))


# ---------------------------------------------------------------------------
# hoofdvenster
# ---------------------------------------------------------------------------
class DraveWeer(QWidget):
    def __init__(self):
        super().__init__()
        self.cfg = load_cfg()
        self.plaats = None
        self._zt = None
        self._wt = None
        self.setWindowTitle("DraveWeer")
        _ic = _res("assets", "icon-256.png")
        if os.path.exists(_ic):
            self.setWindowIcon(QIcon(_ic))
        self.resize(900, 760)
        self.setStyleSheet("background:%s; color:%s;" % (BG, TEXT))
        self._bouw()
        self._maak_tray()
        # laatste plaats laden
        last = self.cfg.get("laatste")
        if last:
            self.plaats = last
            self._toon_plaatsnaam()
            self._haal_weer()
        self._vul_favorieten()
        # automatisch verversen (elke 10 minuten)
        self._auto = QTimer(self)
        self._auto.timeout.connect(self._haal_weer)
        self._auto.start(10 * 60 * 1000)

    # ---- UI opbouwen ----
    def _bouw(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # bovenbalk: zoeken + favorieten
        top = QHBoxLayout()
        self.zoekvak = QLineEdit()
        self.zoekvak.setPlaceholderText("Zoek een plaats...  (bv. Breda)")
        self.zoekvak.setStyleSheet(
            "background:%s; color:%s; border:0; border-radius:8px; padding:10px;"
            "font-size:17px;" % (PANEL, TEXT))
        self.zoekvak.returnPressed.connect(self._zoek)
        top.addWidget(self.zoekvak, 1)
        knop = QPushButton("Zoek")
        knop.setStyleSheet(
            "background:%s; color:#08121c; border:0; border-radius:8px;"
            "padding:10px 16px; font-size:16px; font-weight:bold;" % ACCENT)
        knop.clicked.connect(self._zoek)
        top.addWidget(knop)
        self.favbox = QComboBox()
        self.favbox.setStyleSheet(
            "background:%s; color:%s; border:0; border-radius:8px; padding:8px;"
            "font-size:15px;" % (PANEL, TEXT))
        self.favbox.activated.connect(self._kies_favoriet)
        top.addWidget(self.favbox)
        self.favknop = QPushButton("★ Bewaar")
        self.favknop.setStyleSheet(
            "background:%s; color:%s; border:0; border-radius:8px; padding:10px;"
            "font-size:15px;" % (PANEL, TEXT))
        self.favknop.clicked.connect(self._bewaar_favoriet)
        top.addWidget(self.favknop)
        verv = QPushButton("⟳")
        verv.setToolTip("Nu verversen")
        verv.setStyleSheet(
            "background:%s; color:%s; border:0; border-radius:8px;"
            "padding:10px 14px; font-size:18px;" % (PANEL, TEXT))
        verv.clicked.connect(self._haal_weer)
        top.addWidget(verv)
        root.addLayout(top)

        # zoekresultaten (verschijnen alleen na zoeken)
        self.reslijst = QComboBox()
        self.reslijst.setStyleSheet(
            "background:%s; color:%s; border:0; border-radius:8px; padding:8px;"
            "font-size:15px;" % (PANEL, TEXT))
        self.reslijst.activated.connect(self._kies_resultaat)
        self.reslijst.hide()
        root.addWidget(self.reslijst)

        # huidig-paneel
        paneel = QFrame()
        paneel.setStyleSheet("background:%s; border-radius:16px;" % PANEL)
        pl = QHBoxLayout(paneel)
        pl.setContentsMargins(20, 16, 20, 16)
        pl.setSpacing(16)

        links = QVBoxLayout()
        self.lbl_plaats = QLabel("Zoek een plaats")
        self.lbl_plaats.setStyleSheet("font-size:22px; font-weight:bold;")
        links.addWidget(self.lbl_plaats)
        rij = QHBoxLayout()
        self.icoon = GrootIcoon()
        self.icoon.setFixedSize(120, 120)
        rij.addWidget(self.icoon)
        tempkol = QVBoxLayout()
        self.lbl_temp = QLabel("--°")
        self.lbl_temp.setStyleSheet("font-size:56px; font-weight:bold;")
        tempkol.addWidget(self.lbl_temp)
        self.lbl_oms = QLabel("")
        self.lbl_oms.setStyleSheet("font-size:18px; color:%s;" % SUB)
        tempkol.addWidget(self.lbl_oms)
        rij.addLayout(tempkol)
        rij.addStretch(1)
        links.addLayout(rij)
        self.lbl_extra = QLabel("")
        self.lbl_extra.setStyleSheet("font-size:15px; color:%s;" % SUB)
        links.addWidget(self.lbl_extra)
        links.addStretch(1)
        pl.addLayout(links, 1)

        # metertjes
        meters = QHBoxLayout()
        self.m_temp = Meter("Temperatuur", "°", -10, 40, "#f6c945")
        self.windwijzer = WindWijzer()
        self.m_vocht = Meter("Vocht %", "", 0, 100, "#7ad0a8")
        for m in (self.m_temp, self.windwijzer, self.m_vocht):
            m.setFixedSize(140, 140)
            meters.addWidget(m)
        pl.addLayout(meters)
        root.addWidget(paneel)

        # uitgebreide verwachting in gewone taal (bv. storm met veel regen)
        self.lbl_verwachting = QLabel("")
        self.lbl_verwachting.setWordWrap(True)
        self.lbl_verwachting.setStyleSheet(
            "background:%s; color:%s; border-radius:12px; padding:12px 16px;"
            "font-size:19px;" % (PANEL, TEXT))
        self.lbl_verwachting.hide()
        root.addWidget(self.lbl_verwachting)

        # uurverwachting
        lbl_u = QLabel("Vandaag per uur")
        lbl_u.setStyleSheet("font-size:16px; font-weight:bold; color:%s;" % SUB)
        root.addWidget(lbl_u)
        self.grafiek = UurGrafiek()
        gframe = QFrame()
        gframe.setStyleSheet("background:%s; border-radius:14px;" % PANEL)
        gl = QVBoxLayout(gframe)
        gl.setContentsMargins(8, 8, 8, 8)
        gl.addWidget(self.grafiek)
        root.addWidget(gframe)

        # 7-daagse
        lbl_d = QLabel("Komende dagen")
        lbl_d.setStyleSheet("font-size:16px; font-weight:bold; color:%s;" % SUB)
        root.addWidget(lbl_d)
        dagrij = QHBoxLayout()
        dagrij.setSpacing(8)
        self.kaarten = []
        for _ in range(7):
            k = DagKaart()
            self.kaarten.append(k)
            dagrij.addWidget(k)
        root.addLayout(dagrij)

        self.status = QLabel("")
        self.status.setStyleSheet("color:%s; font-size:13px;" % SUB)
        root.addWidget(self.status)

    # ---- zoeken ----
    def _zoek(self):
        naam = self.zoekvak.text().strip()
        if not naam:
            return
        self.status.setText("Zoeken...")
        self._zt = ZoekThread(naam)
        self._zt.klaar.connect(self._zoek_klaar)
        self._zt.start()

    def _zoek_klaar(self, res):
        if not res:
            self.status.setText("Geen plaats gevonden. Probeer een andere naam.")
            self.reslijst.hide()
            return
        self._res = res
        self.reslijst.clear()
        for r in res:
            stuk = [r["naam"]]
            if r["regio"]:
                stuk.append(r["regio"])
            if r["land"]:
                stuk.append(r["land"])
            self.reslijst.addItem(", ".join(stuk))
        self.reslijst.show()
        self.status.setText("Kies de juiste plaats hierboven.")
        self._kies_resultaat(0)

    def _kies_resultaat(self, i):
        if not getattr(self, "_res", None) or i < 0 or i >= len(self._res):
            return
        r = self._res[i]
        self.plaats = {"naam": r["naam"], "land": r["land"], "regio": r["regio"],
                       "lat": r["lat"], "lon": r["lon"]}
        self._toon_plaatsnaam()
        self.cfg["laatste"] = self.plaats
        save_cfg(self.cfg)
        self._haal_weer()

    # ---- favorieten ----
    def _vul_favorieten(self):
        self.favbox.blockSignals(True)
        self.favbox.clear()
        self.favbox.addItem("★ Favorieten...")
        for f in self.cfg.get("favorieten", []):
            self.favbox.addItem(f["naam"])
        self.favbox.blockSignals(False)

    def _kies_favoriet(self, i):
        favs = self.cfg.get("favorieten", [])
        if i <= 0 or i - 1 >= len(favs):
            return
        self.plaats = favs[i - 1]
        self._toon_plaatsnaam()
        self.cfg["laatste"] = self.plaats
        save_cfg(self.cfg)
        self._haal_weer()

    def _bewaar_favoriet(self):
        if not self.plaats:
            return
        favs = self.cfg.setdefault("favorieten", [])
        if any(f.get("naam") == self.plaats["naam"] for f in favs):
            self.status.setText("Staat al bij je favorieten.")
            return
        favs.append(self.plaats)
        save_cfg(self.cfg)
        self._vul_favorieten()
        self.status.setText("Toegevoegd aan favorieten: " + self.plaats["naam"])

    # ---- weer tonen ----
    def _toon_plaatsnaam(self):
        if not self.plaats:
            return
        naam = self.plaats["naam"]
        if self.plaats.get("land"):
            naam += ", " + self.plaats["land"]
        self.lbl_plaats.setText(naam)

    def _haal_weer(self):
        if not self.plaats:
            return
        self.status.setText("Weer ophalen...")
        self._wt = WeerThread(self.plaats["lat"], self.plaats["lon"])
        self._wt.klaar.connect(self._weer_klaar)
        self._wt.start()

    def _weer_klaar(self, data):
        if not data:
            self.status.setText("Kon het weer niet ophalen. Controleer je internet.")
            return
        h = data["huidig"]
        self.icoon.set(h["icoon"], h["dag"])
        self.lbl_temp.setText("%d°" % round(h["temp"]) if h["temp"] is not None else "--°")
        self.lbl_oms.setText(h["oms"])
        extra = []
        if h.get("gevoel") is not None:
            extra.append("Gevoel %d°" % round(h["gevoel"]))
        if h.get("stoten") is not None and h["stoten"] >= 40:
            extra.append("stoten %d km/u" % round(h["stoten"]))
        if h.get("op"):
            extra.append("op %s" % h["op"])
        if h.get("onder"):
            extra.append("onder %s" % h["onder"])
        self.lbl_extra.setText("   ·   ".join(extra))
        self.m_temp.set_value(h.get("temp"))
        self.windwijzer.set_wind(h.get("wind"), h.get("windricht"))
        self.m_vocht.set_value(h.get("vocht"))
        self.grafiek.set_uur(data["uur"])
        for k, d in zip(self.kaarten, data["dagen"]):
            k.set_dag(d)
            k.setToolTip(d.get("tekst", ""))
        self._toon_verwachting(data["dagen"])
        self.status.setText("Bijgewerkt om " + datetime.datetime.now().strftime("%H:%M")
                            + "  ·  ververst automatisch elke 10 min")
        self._werk_tray_bij(h, data["dagen"])

    def _toon_verwachting(self, dagen):
        """Toon vandaag (en morgen) in gewone taal; bij storm/onweer in waarschuwingskleur."""
        if not dagen:
            self.lbl_verwachting.hide()
            return
        regels = [dagen[0].get("tekst", "")]
        if len(dagen) > 1:
            regels.append(dagen[1].get("tekst", ""))
        w = max(d.get("waarschuwing", 0) for d in dagen[:2])
        if w >= 2:
            rand, voor = "#e8613c", "\u26a0  "
        elif w == 1:
            rand, voor = "#f6c945", ""
        else:
            rand, voor = PANEL, ""
        self.lbl_verwachting.setText(voor + "\n".join(r for r in regels if r))
        self.lbl_verwachting.setStyleSheet(
            "background:%s; color:%s; border:2px solid %s; border-radius:12px;"
            "padding:12px 16px; font-size:19px;" % (PANEL, TEXT, rand))
        self.lbl_verwachting.show()

    # ---- systeemvak (taakbalk) ----
    def _maak_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(QIcon(_res("assets", "icon-256.png")))
        self.tray.setToolTip("DraveWeer")
        m = QMenu()
        a_open = QAction("Openen", self)
        a_open.triggered.connect(self._toon_venster)
        a_verv = QAction("Ververs", self)
        a_verv.triggered.connect(self._haal_weer)
        a_uit = QAction("Afsluiten", self)
        a_uit.triggered.connect(QApplication.quit)
        m.addAction(a_open)
        m.addAction(a_verv)
        m.addSeparator()
        m.addAction(a_uit)
        self.tray.setContextMenu(m)
        self.tray.activated.connect(self._tray_klik)
        self.tray.show()
        self._tray_gemeld = False

    def _tray_klik(self, reden):
        if reden == QSystemTrayIcon.ActivationReason.Trigger:
            self._toon_venster()

    def _toon_venster(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _temp_kleur(self, t):
        if t is None:
            return QColor("#5a6a7a")
        for grens, kleur in ((0, "#4a78d6"), (10, "#4aa6d6"), (18, "#3fb08a"),
                             (25, "#e6a93a"), (30, "#e6772f")):
            if t < grens:
                return QColor(kleur)
        return QColor("#d9442f")

    def _tray_icoon(self, temp):
        pm = QPixmap(64, 64)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._temp_kleur(temp))
        p.drawRoundedRect(2, 2, 60, 60, 16, 16)
        p.setPen(QColor("#ffffff"))
        txt = "--" if temp is None else "%d°" % round(temp)
        p.setFont(QFont("Segoe UI", 34 if len(txt) <= 3 else 27, QFont.Weight.Bold))
        p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, txt)
        p.end()
        return QIcon(pm)

    def _werk_tray_bij(self, h, dagen=None):
        if not getattr(self, "tray", None):
            return
        self.tray.setIcon(self._tray_icoon(h.get("temp")))
        naam = self.plaats["naam"] if self.plaats else ""
        t = "--" if h.get("temp") is None else "%d°" % round(h["temp"])
        tip = "%s  %s  %s" % (naam, t, h.get("oms", ""))
        if h.get("wind") is not None:
            tip += "\nWind %d km/u %s" % (round(h["wind"]), kompas(h.get("windricht")))
        if dagen and dagen[0].get("tekst"):
            tip += "\n" + dagen[0]["tekst"]
        self.tray.setToolTip(tip[:250])

    def closeEvent(self, e):
        # niet echt afsluiten: verbergen naar het systeemvak (blijft de temp tonen)
        if getattr(self, "tray", None) and self.tray.isVisible():
            e.ignore()
            self.hide()
            if not self._tray_gemeld:
                self._tray_gemeld = True
                self.tray.showMessage(
                    "DraveWeer",
                    "Draait verder in het systeemvak. Rechtsklik het icoon om af te sluiten.",
                    QSystemTrayIcon.MessageIcon.Information, 4000)
        else:
            e.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("DraveWeer")
    app.setQuitOnLastWindowClosed(False)   # blijft in het systeemvak draaien
    w = DraveWeer()
    try:
        import drave_doneer
        drave_doneer.voeg_toe(w)
    except Exception:
        pass
    w.show()
    try:  # Dravenlock: stille update-check (uit te zetten; Ctrl+Shift+U = met de hand)
        import drave_update
        drave_update.start(w, 'DraveWeer', '1.1.1')
    except Exception:
        pass
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
