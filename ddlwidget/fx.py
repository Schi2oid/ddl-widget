"""完成任务的庆祝特效：飞行卡片 + 礼花粒子。

实现要点：
  * 一个全屏、点击穿透、不抢焦点的透明浮层负责绘制；
  * 粒子有重力、空气阻力、旋转与淡出，形状混用方形 / 长条 / 圆点；
  * 落地时追加一个扩散光环，强化「炸开」的感觉。
"""

from __future__ import annotations

import math
import random
import sys
import time
from dataclasses import dataclass, field
from typing import Callable

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from . import theme

CONFETTI_COLORS = [
    "#7C8CFF", "#A78BFA", "#FFB35C", "#4ADE80",
    "#FF5C6B", "#5CACFF", "#F472B6", "#FFE27A", "#FFFFFF",
]

GRAVITY = 1150.0
DRAG = 0.988


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    size: float
    color: QColor
    life: float
    age: float = 0.0
    rot: float = 0.0
    vrot: float = 0.0
    shape: str = "rect"
    flutter: float = 0.0


@dataclass
class Ring:
    x: float
    y: float
    radius: float
    color: QColor
    life: float
    age: float = 0.0
    filled: bool = False
    speed: float = 320.0


@dataclass
class Flyer:
    pixmap: QPixmap
    start: QPointF
    end: QPointF
    ctrl: QPointF
    duration: float
    on_done: Callable[[], None] | None = None
    age: float = 0.0
    spin: float = 0.0


def solid_card(source: QPixmap, radius: float = 12.0) -> QPixmap:
    """把半透明的行快照压到一张不透明圆角卡片上，飞行时不会透出底下的文字。"""
    dpr = source.devicePixelRatio() or 1.0
    width = source.width() / dpr
    height = source.height() / dpr
    card = QPixmap(source.size())
    card.setDevicePixelRatio(dpr)
    card.fill(Qt.GlobalColor.transparent)
    painter = QPainter(card)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(25, 27, 38, 250))
    painter.drawRoundedRect(QRectF(0, 0, width, height), radius, radius)
    painter.drawPixmap(0, 0, source)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor(140, 155, 255, 90), 1.2))
    painter.drawRoundedRect(QRectF(0.6, 0.6, width - 1.2, height - 1.2), radius, radius)
    painter.end()
    return card


def check_chip(size: int = 64) -> QPixmap:
    """同步发现完成时用的「✓」小卡片。"""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    rect = QRectF(1, 1, size - 2, size - 2)
    painter.setPen(QPen(QColor(255, 255, 255, 40), 1))
    painter.setBrush(QColor(24, 26, 36, 246))
    painter.drawRoundedRect(rect, size * 0.28, size * 0.28)
    painter.setPen(
        QPen(
            QColor(theme.GREEN),
            size * 0.09,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
    )
    path_x, path_y = size * 0.28, size * 0.52
    painter.drawLine(
        QPointF(path_x, path_y), QPointF(size * 0.44, size * 0.66)
    )
    painter.drawLine(
        QPointF(size * 0.44, size * 0.66), QPointF(size * 0.73, size * 0.34)
    )
    painter.end()
    return pixmap


class FxOverlay(QWidget):
    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowTransparentForInput,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        if sys.platform == "darwin":
            self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._particles: list[Particle] = []
        self._rings: list[Ring] = []
        self._flyers: list[Flyer] = []
        self._chip = check_chip()

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._step)
        self._last = time.monotonic()

    # ------------------------------------------------------------------
    def is_animating(self) -> bool:
        return self._timer.isActive()

    def _ensure_visible(self, *points: QPoint) -> None:
        anchor = points[0] if points else QCursor_pos()
        screen = QGuiApplication.screenAt(anchor) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        if self.geometry() != area:
            self.setGeometry(area)
        if not self.isVisible():
            self.show()
        self.raise_()
        if not self._timer.isActive():
            self._last = time.monotonic()
            self._timer.start()

    # ------------------------------------------------------------------
    def burst(self, global_pos: QPoint, count: int = 90, power: float = 1.0) -> None:
        self._ensure_visible(global_pos)
        origin = self.mapFromGlobal(global_pos)
        self._spawn(origin.x(), origin.y(), count, power)
        self._rings.append(
            Ring(origin.x(), origin.y(), 18.0, QColor(255, 255, 255), 0.12, filled=True, speed=220.0)
        )
        self._rings.append(
            Ring(origin.x(), origin.y(), 4.0, QColor(theme.ACCENT_SOFT), 0.30, speed=560.0)
        )
        self.update()

    def sparkle(self, global_pos: QPoint, count: int = 12) -> None:
        self._ensure_visible(global_pos)
        origin = self.mapFromGlobal(global_pos)
        self._spawn(origin.x(), origin.y(), count, 0.45)
        self.update()

    def fly(
        self,
        pixmap: QPixmap | None,
        start_global: QPoint,
        end_global: QPoint,
        duration: float = 0.62,
        on_done: Callable[[], None] | None = None,
    ) -> None:
        self._ensure_visible(start_global, end_global)
        start = QPointF(self.mapFromGlobal(start_global))
        end = QPointF(self.mapFromGlobal(end_global))
        mid_x = (start.x() + end.x()) / 2
        ctrl = QPointF(mid_x, min(start.y(), end.y()) - 110)
        self._flyers.append(
            Flyer(
                pixmap=pixmap or self._chip,
                start=start,
                end=end,
                ctrl=ctrl,
                duration=duration,
                on_done=on_done,
                spin=random.uniform(-10.0, 10.0),
            )
        )
        self.update()

    # ------------------------------------------------------------------
    def _spawn(self, x: float, y: float, count: int, power: float) -> None:
        for _ in range(count):
            angle = random.uniform(-math.pi * 0.95, -math.pi * 0.05)
            speed = random.uniform(200.0, 760.0) * power
            shape = random.choices(("rect", "ribbon", "dot"), weights=(5, 3, 2))[0]
            size = random.uniform(3.5, 8.5)
            self._particles.append(
                Particle(
                    x=x + random.uniform(-6, 6),
                    y=y + random.uniform(-6, 6),
                    vx=math.cos(angle) * speed,
                    vy=math.sin(angle) * speed,
                    size=size,
                    color=QColor(random.choice(CONFETTI_COLORS)),
                    life=random.uniform(0.85, 1.65),
                    rot=random.uniform(0, 360),
                    vrot=random.uniform(-520, 520),
                    shape=shape,
                    flutter=random.uniform(0, math.tau),
                )
            )

    def _step(self) -> None:
        now = time.monotonic()
        dt = min(0.05, max(0.001, now - self._last))
        self._last = now

        alive: list[Particle] = []
        for p in self._particles:
            p.age += dt
            if p.age >= p.life:
                continue
            p.vy += GRAVITY * dt
            p.vx *= DRAG
            p.vy *= DRAG
            p.x += p.vx * dt + math.sin(p.age * 9 + p.flutter) * 14 * dt
            p.y += p.vy * dt
            p.rot += p.vrot * dt
            alive.append(p)
        self._particles = alive

        self._rings = [r for r in (self._age_ring(r, dt) for r in self._rings) if r]

        arrived: list[Callable[[], None]] = []
        flyers: list[Flyer] = []
        for f in self._flyers:
            f.age += dt
            progress = min(1.0, f.age / f.duration)
            fx, fy = _flyer_pos(f, 1 - (1 - progress) ** 3)
            if f.age < f.duration and random.random() < 0.6:
                self._particles.append(
                    Particle(
                        x=fx,
                        y=fy,
                        vx=random.uniform(-40, 40),
                        vy=random.uniform(-50, 20),
                        size=random.uniform(1.8, 3.6),
                        color=QColor(random.choice(CONFETTI_COLORS)),
                        life=random.uniform(0.3, 0.6),
                        shape="dot",
                    )
                )
            if f.age >= f.duration:
                arrived.append(f.on_done) if f.on_done else None
                landed = QPoint(int(f.end.x()), int(f.end.y()))
                self._spawn(f.end.x(), f.end.y(), 26, 0.5)
                self._rings.append(
                    Ring(f.end.x(), f.end.y(), 4.0, QColor(theme.GREEN), 0.5)
                )
                continue
            flyers.append(f)
        self._flyers = flyers

        for callback in arrived:
            callback()

        if not self._particles and not self._flyers and not self._rings:
            self._timer.stop()
            self.hide()
            return
        self.update()

    @staticmethod
    def _age_ring(ring: Ring, dt: float) -> Ring | None:
        ring.age += dt
        if ring.age >= ring.life:
            return None
        ring.radius += dt * ring.speed
        return ring

    # ------------------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        for ring in self._rings:
            t = ring.age / ring.life
            color = QColor(ring.color)
            if ring.filled:
                color.setAlphaF(max(0.0, (1.0 - t) * 0.30))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(color)
                painter.drawEllipse(QPointF(ring.x, ring.y), ring.radius, ring.radius)
            else:
                color.setAlphaF(max(0.0, ((1.0 - t) ** 1.6) * 0.6))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(color, 1.2 + 2.0 * (1 - t)))
                painter.drawEllipse(QPointF(ring.x, ring.y), ring.radius, ring.radius)

        for f in self._flyers:
            done = min(1.0, f.age / f.duration)
            eased = 1 - (1 - done) ** 3
            x, y = _flyer_pos(f, eased)
            scale = 0.92 - 0.50 * eased
            dpr = f.pixmap.devicePixelRatio() or 1.0
            width = (f.pixmap.width() / dpr) * scale
            height = (f.pixmap.height() / dpr) * scale
            painter.save()
            painter.setOpacity(1.0 if eased < 0.88 else max(0.0, (1.0 - eased) / 0.12))
            painter.translate(x, y)
            painter.rotate(f.spin * math.sin(eased * math.pi))
            shadow = QRectF(-width / 2 + 2, -height / 2 + 6, width, height)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, 80))
            painter.drawRoundedRect(shadow, 12 * scale, 12 * scale)
            target = QRectF(-width / 2, -height / 2, width, height)
            painter.drawPixmap(target, f.pixmap, QRectF(f.pixmap.rect()))
            painter.restore()

        painter.setPen(Qt.PenStyle.NoPen)
        for p in self._particles:
            fade = 1.0
            remain = p.life - p.age
            if remain < 0.35:
                fade = max(0.0, remain / 0.35)
            color = QColor(p.color)
            color.setAlphaF(fade)
            painter.save()
            painter.translate(p.x, p.y)
            painter.rotate(p.rot)
            painter.setBrush(color)
            if p.shape == "dot":
                painter.drawEllipse(QRectF(-p.size / 2, -p.size / 2, p.size, p.size))
            elif p.shape == "ribbon":
                painter.drawRoundedRect(QRectF(-p.size, -p.size * 0.35, p.size * 2, p.size * 0.7), 1.2, 1.2)
            else:
                painter.drawRect(QRectF(-p.size / 2, -p.size / 2, p.size, p.size * 0.72))
            painter.restore()


def _flyer_pos(flyer: Flyer, eased: float) -> tuple[float, float]:
    x = (
        (1 - eased) ** 2 * flyer.start.x()
        + 2 * (1 - eased) * eased * flyer.ctrl.x()
        + eased**2 * flyer.end.x()
    )
    y = (
        (1 - eased) ** 2 * flyer.start.y()
        + 2 * (1 - eased) * eased * flyer.ctrl.y()
        + eased**2 * flyer.end.y()
    )
    return x, y


def QCursor_pos() -> QPoint:  # noqa: N802
    from PySide6.QtGui import QCursor

    return QCursor.pos()
