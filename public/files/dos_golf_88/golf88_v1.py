#!/usr/bin/env python3
"""
DOS-style golf game inspired by 1988-1992 PC releases.
Top-down hole maps, CGA/EGA palette, swing meter, shot tracer, scoreboard, and
ball-flight animation evoke suitcase-style luggable PC golf sims.
"""

from __future__ import annotations

import math
import random
import textwrap
import tkinter as tk
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

try:
    from tkinter import messagebox
except ImportError:  # pragma: no cover - missing on some minimal builds
    messagebox = None

# --- Constants --------------------------------------------------------------

CELL_YARDS = 5.0  # each tile ~= 5 yards of ground
FLAG_CAPTURE_RADIUS = 1.6  # yards to consider the cup holed
GREEN_RANGE_YARDS = 34.0  # auto putter distance when on the green
MAX_AIM_DEGREES = 12

POWER_LIMITS = {
    "full": (30, 110),
    "putt": (10, 120),
}

LIE_EFFECTS: Dict[str, float] = {
    "tee": 1.05,
    "fairway": 1.0,
    "rough": 0.82,
    "sand": 0.58,
    "green": 0.5,
}

LIE_SPIN_PENALTY: Dict[str, float] = {
    "tee": 1.0,
    "fairway": 1.0,
    "rough": 1.15,
    "sand": 1.28,
    "green": 0.92,
}

SHOT_MESSAGES = {
    "tee": "Teed up nicely.",
    "fairway": "Ball finds the short grass.",
    "rough": "It hops into the rough.",
    "sand": "Splash of sand – bunker duty.",
    "green": "You're on the dance floor!",
}

TILE_TO_LIE = {
    "T": "tee",
    "=": "fairway",
    "-": "fairway",
    ".": "rough",
    "^": "rough",
    "#": "rough",
    "S": "sand",
    "G": "green",
    "H": "green",
}

TILE_COLORS = {
    "T": "#1E5F5F",
    "=": "#2CA84D",
    "-": "#2CA84D",
    ".": "#0F4A2A",
    "^": "#08361C",
    "#": "#08361C",
    "S": "#C6A45A",
    "G": "#6FF26F",
    "H": "#F0EC64",
    "~": "#194F9A",
    " ": "#021212",
}

# --- Data classes -----------------------------------------------------------


@dataclass(frozen=True)
class Club:
    name: str
    base_distance: float  # yards
    accuracy: float  # standard deviation in degrees
    roll: float  # yards of rollout after carry
    for_putting: bool = False


@dataclass(frozen=True)
class Hole:
    name: str
    par: int
    yardage: int
    layout: Sequence[str]
    tee: Tuple[int, int]
    cup: Tuple[int, int]
    wind_speed: int  # mph
    wind_direction: int  # degrees; 0=E, 90=S, 180=W, 270=N

    @property
    def width(self) -> int:
        return len(self.layout[0])

    @property
    def height(self) -> int:
        return len(self.layout)


@dataclass
class ShotResult:
    position: Tuple[float, float]
    lie: str
    holed: bool
    strokes: int
    message: str
    carry: float = 0.0
    roll: float = 0.0
    wind_drift: float = 0.0
    total: float = 0.0
    penalty: bool = False


# --- Geometry & formatting helpers -----------------------------------------


def format_score(score: int) -> str:
    if score == 0:
        return "E"
    prefix = "+" if score > 0 else ""
    return f"{prefix}{score}"


def angle_to(target: Tuple[float, float], origin: Tuple[float, float]) -> float:
    return math.atan2(target[1] - origin[1], target[0] - origin[0])


def distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.hypot((a[0] - b[0]) * CELL_YARDS, (a[1] - b[1]) * CELL_YARDS)


def layout_tile(hole: Hole, coord: Tuple[int, int]) -> str:
    x, y = coord
    if 0 <= y < hole.height and 0 <= x < hole.width:
        return hole.layout[y][x]
    return " "


def lie_for_tile(tile: str) -> str:
    if tile == "~":
        return "water"
    return TILE_TO_LIE.get(tile, "rough")


def format_wind(speed: int, direction: int) -> str:
    bearings = [
        (0, "E"),
        (45, "SE"),
        (90, "S"),
        (135, "SW"),
        (180, "W"),
        (225, "NW"),
        (270, "N"),
        (315, "NE"),
        (360, "E"),
    ]
    for idx in range(len(bearings) - 1):
        low, label = bearings[idx]
        high, _ = bearings[idx + 1]
        if low <= direction < high:
            return f"{speed} mph {label}"
    return f"{speed} mph"


def clamp(val: float, low: float, high: float) -> float:
    return max(low, min(high, val))


def segment_distance_to_point(
    start: Tuple[float, float], end: Tuple[float, float], point: Tuple[float, float]
) -> float:
    sx, sy = start
    ex, ey = end
    px, py = point
    vx = ex - sx
    vy = ey - sy
    wx = px - sx
    wy = py - sy
    seg_len_sq = vx * vx + vy * vy
    if seg_len_sq == 0:
        return math.hypot(wx, wy)
    t = (vx * wx + vy * wy) / seg_len_sq
    t = clamp(t, 0.0, 1.0)
    closest_x = sx + vx * t
    closest_y = sy + vy * t
    return math.hypot(closest_x - px, closest_y - py)


# --- Shot simulation --------------------------------------------------------


def wind_vector(hole: Hole, club: Club, rng: random.Random) -> Tuple[float, float]:
    if club.for_putting or hole.wind_speed == 0:
        return 0.0, 0.0
    wind_scale = hole.wind_speed / 13.0
    club_factor = clamp(club.base_distance / 220.0, 0.4, 1.35)
    drift = wind_scale * club_factor * rng.uniform(0.55, 1.22)
    direction_rad = math.radians(hole.wind_direction)
    return math.cos(direction_rad) * drift, math.sin(direction_rad) * drift


def simulate_shot(
    ball: Tuple[float, float],
    hole: Hole,
    club: Club,
    power: int,
    lie: str,
    aim_adjust: int,
    rng: random.Random,
) -> ShotResult:
    cup_center = (hole.cup[0] + 0.5, hole.cup[1] + 0.5)
    base_angle = angle_to(cup_center, ball)
    intended = base_angle + math.radians(aim_adjust)
    spray = rng.gauss(0.0, math.radians(club.accuracy * LIE_SPIN_PENALTY.get(lie, 1.0)))
    shot_angle = intended + spray

    lie_effect = LIE_EFFECTS.get(lie, 0.8)
    carry_yards = 0.0
    roll_yards = 0.0
    wind_shift_cells = (0.0, 0.0)

    if club.for_putting:
        base_feet = club.base_distance * (power / 100.0)
        noisy_feet = clamp(base_feet + rng.gauss(0, base_feet * 0.08), 0, 95)
        yards = noisy_feet / 3.0
        dx = math.cos(shot_angle) * (yards / CELL_YARDS)
        dy = math.sin(shot_angle) * (yards / CELL_YARDS)
        carry_yards = yards
        roll_yards = 0.0
    else:
        base_yards = club.base_distance * (power / 100.0) * lie_effect
        carry_yards = max(4.0, base_yards + rng.gauss(0, club.base_distance * 0.1))
        roll_yards = club.roll * (power / 100.0) * max(0.45, lie_effect)
        total_yards = carry_yards + roll_yards
        dx = math.cos(shot_angle) * (total_yards / CELL_YARDS)
        dy = math.sin(shot_angle) * (total_yards / CELL_YARDS)
        wind_dx, wind_dy = wind_vector(hole, club, rng)
        dx += wind_dx
        dy += wind_dy
        wind_shift_cells = (wind_dx, wind_dy)

    new_x = ball[0] + dx
    new_y = ball[1] + dy

    tile = layout_tile(hole, (int(round(new_x)), int(round(new_y))))
    wind_yards = math.hypot(wind_shift_cells[0] * CELL_YARDS, wind_shift_cells[1] * CELL_YARDS)

    if tile == "~":
        return ShotResult(
            position=ball,
            lie=lie,
            holed=False,
            strokes=2,
            message="Splash! Water hazard. Drop beside the point of entry.",
            carry=carry_yards,
            roll=roll_yards,
            wind_drift=wind_yards,
            total=carry_yards + roll_yards,
            penalty=True,
        )
    if tile == " ":
        return ShotResult(
            position=ball,
            lie=lie,
            holed=False,
            strokes=2,
            message="Out of bounds. Stroke and distance.",
            carry=carry_yards,
            roll=roll_yards,
            wind_drift=wind_yards,
            total=carry_yards + roll_yards,
            penalty=True,
        )

    new_position = (new_x, new_y)
    segment_dist = segment_distance_to_point(ball, new_position, cup_center)

    if tile == "H" or segment_dist * CELL_YARDS <= FLAG_CAPTURE_RADIUS:
        return ShotResult(
            position=cup_center,
            lie="cup",
            holed=True,
            strokes=1,
            message="Tin cup clank – it's in!",
            carry=carry_yards,
            roll=roll_yards,
            wind_drift=wind_yards,
            total=carry_yards + roll_yards,
            penalty=False,
        )

    new_lie = lie_for_tile(tile)
    new_lie = "green" if tile in {"G", "H"} else new_lie

    return ShotResult(
        position=new_position,
        lie=new_lie,
        holed=False,
        strokes=1,
        message=SHOT_MESSAGES.get(new_lie, "Ball comes to rest."),
        carry=carry_yards,
        roll=roll_yards,
        wind_drift=wind_yards,
        total=carry_yards + roll_yards,
        penalty=False,
    )


# --- Game UI ----------------------------------------------------------------


class GameApp:
    TILE_SIZE = 16
    BG_COLOR = "#011A1A"
    HUD_BG = "#033232"
    HUD_FG = "#8CF2F2"
    STATUS_FG = "#F2E48A"
    LEGEND_FG = "#4DE1BE"

    def __init__(self, course: Sequence[Hole], clubs: Sequence[Club]) -> None:
        self.course = course
        self.clubs = clubs
        self.hole_index = 0
        self.hole = self.course[0]
        self.rng = random.Random()
        self.rng.seed()

        self.ball_position: Tuple[float, float] = (self.hole.tee[0] + 0.5, self.hole.tee[1] + 0.5)
        self.lie = "tee"
        self.hole_strokes = 0
        self.completed_strokes = 0
        self.total_relative = 0
        self.current_club_idx = 0
        self.aim_degrees = 0
        self.last_message = "Welcome back to 1990."

        self.power_meter_active = False
        self.power_value = POWER_LIMITS["full"][0]
        self.power_direction = 1
        self.awaiting_next = False
        self.animating_shot = False

        self.root = tk.Tk()
        self.root.title("DOS Golf Pro Tour '90")
        self.root.configure(bg=self.BG_COLOR)
        self.root.resizable(False, False)

        self.hud_var = tk.StringVar()
        self.info_var = tk.StringVar()
        self.detail_var = tk.StringVar()
        self.club_info_var = tk.StringVar()
        self.controls_var = tk.StringVar()
        self.status_var = tk.StringVar()
        self.shot_summary_var = tk.StringVar()
        self.next_prompt_var = tk.StringVar()
        self.scoreboard_var = tk.StringVar()

        self._build_layout_widgets()
        self._bind_keys()

        self.ball_sprite: int | None = None
        self.ball_shadow: int | None = None
        self.aim_indicator: int | None = None
        self.target_indicator: int | None = None
        self.tracer_items: List[int] = []
        self.scorecard: List[Tuple[int, int]] = []

        self.wind_string = format_wind(self.hole.wind_speed, self.hole.wind_direction)
        self.load_hole(0)

    # -- UI construction -----------------------------------------------------

    def _build_layout_widgets(self) -> None:
        top = tk.Frame(self.root, bg=self.HUD_BG, bd=2, relief="ridge")
        top.pack(fill="x", padx=10, pady=(8, 4))

        tk.Label(top, textvariable=self.hud_var, anchor="w", fg=self.HUD_FG, bg=self.HUD_BG,
                 font=("IBM Plex Mono", 12, "bold"), padx=6).pack(fill="x")
        tk.Label(top, textvariable=self.info_var, anchor="w", fg=self.HUD_FG, bg=self.HUD_BG,
                 font=("IBM Plex Mono", 10), padx=6).pack(fill="x")
        tk.Label(top, textvariable=self.detail_var, anchor="w", fg=self.HUD_FG, bg=self.HUD_BG,
                 font=("IBM Plex Mono", 10), padx=6).pack(fill="x")
        tk.Label(top, textvariable=self.club_info_var, anchor="w", fg=self.HUD_FG, bg=self.HUD_BG,
                 font=("IBM Plex Mono", 10), padx=6).pack(fill="x")

        width = self.hole.width * self.TILE_SIZE
        height = self.hole.height * self.TILE_SIZE
        canvas_frame = tk.Frame(self.root, bg=self.BG_COLOR, bd=2, relief="ridge")
        canvas_frame.pack(padx=10, pady=(0, 6))
        self.canvas = tk.Canvas(canvas_frame, width=width, height=height, bg="#001010",
                                highlightthickness=0)
        self.canvas.pack()

        meter_frame = tk.Frame(self.root, bg=self.BG_COLOR)
        meter_frame.pack(fill="x", padx=10)
        self.power_canvas = tk.Canvas(meter_frame, width=width, height=26, bg="#052222",
                                      highlightthickness=1, highlightbackground="#0A3F3F")
        self.power_canvas.pack()

        bottom = tk.Frame(self.root, bg=self.HUD_BG, bd=2, relief="ridge")
        bottom.pack(fill="x", padx=10, pady=(4, 8))
        tk.Label(bottom, textvariable=self.controls_var, anchor="w", fg=self.HUD_FG, bg=self.HUD_BG,
                 font=("IBM Plex Mono", 10), padx=6).pack(fill="x")
        tk.Label(bottom, textvariable=self.status_var, anchor="w", fg=self.STATUS_FG, bg=self.HUD_BG,
                 font=("IBM Plex Mono", 10), padx=6).pack(fill="x")
        tk.Label(bottom, textvariable=self.shot_summary_var, anchor="w", fg=self.HUD_FG, bg=self.HUD_BG,
                 font=("IBM Plex Mono", 10), padx=6).pack(fill="x")
        tk.Label(bottom, textvariable=self.next_prompt_var, anchor="w", fg=self.LEGEND_FG, bg=self.HUD_BG,
                 font=("IBM Plex Mono", 10), padx=6).pack(fill="x")

        scoreboard_frame = tk.Frame(self.root, bg=self.BG_COLOR, bd=1, relief="ridge")
        scoreboard_frame.pack(fill="x", padx=10, pady=(0, 8))
        tk.Label(scoreboard_frame, textvariable=self.scoreboard_var, justify="left",
                 fg="#89F2C9", bg=self.BG_COLOR, font=("IBM Plex Mono", 10), padx=6, pady=4).pack(fill="x")

        legend = "Legend: Tee teal | Fairway bright green | Rough dark | Sand gold | Green neon | Water blue"
        tk.Label(self.root, text=legend, fg=self.LEGEND_FG, bg=self.BG_COLOR,
                 font=("IBM Plex Mono", 9)).pack(pady=(0, 6))

    def _bind_keys(self) -> None:
        self.root.bind("<Left>", self.on_left)
        self.root.bind("<Right>", self.on_right)
        self.root.bind("<KeyPress-bracketleft>", self.on_prev_club)
        self.root.bind("<KeyPress-bracketright>", self.on_next_club)
        self.root.bind("<KeyPress-comma>", self.on_prev_club)
        self.root.bind("<KeyPress-period>", self.on_next_club)
        self.root.bind("<space>", self.on_space)
        self.root.bind("<Return>", self.on_return)
        self.root.bind("<KeyPress-Escape>", lambda _evt: self.root.destroy())

    # -- Core state ----------------------------------------------------------

    def load_hole(self, index: int) -> None:
        self.hole_index = index
        self.hole = self.course[index]
        self.ball_position = (self.hole.tee[0] + 0.5, self.hole.tee[1] + 0.5)
        self.lie = "tee"
        self.hole_strokes = 0
        self.aim_degrees = 0
        self.wind_string = format_wind(self.hole.wind_speed, self.hole.wind_direction)
        self.awaiting_next = False
        self.animating_shot = False
        self.last_message = "Set your opening shot." if index == 0 else "New tee shot."
        self.shot_summary_var.set("")
        self.next_prompt_var.set("")

        for item in self.tracer_items:
            self.canvas.delete(item)
        self.tracer_items.clear()

        self._redraw_course()
        self._spawn_ball()
        self._ensure_valid_club()
        self._update_hud()
        self._update_meter_visual()
        self._refresh_scoreboard()
        self.status_var.set(self.last_message)

    def _redraw_course(self) -> None:
        self.canvas.delete("all")
        tile = self.TILE_SIZE
        for y, row in enumerate(self.hole.layout):
            for x, ch in enumerate(row):
                color = TILE_COLORS.get(ch, "#08361C")
                self.canvas.create_rectangle(
                    x * tile,
                    y * tile,
                    (x + 1) * tile,
                    (y + 1) * tile,
                    fill=color,
                    outline="#022222",
                )
        cx, cy = self.hole.cup
        flag = self.canvas.create_rectangle(
            cx * tile + tile * 0.3,
            cy * tile + tile * 0.3,
            cx * tile + tile * 0.7,
            cy * tile + tile * 0.7,
            fill="#FFF48A",
            outline="#493C00",
        )
        pole = self.canvas.create_line(
            cx * tile + tile * 0.55,
            cy * tile + tile * 0.2,
            cx * tile + tile * 0.55,
            cy * tile - tile * 0.9,
            width=2,
            fill="#F5E9DB",
        )
        pennant = self.canvas.create_polygon(
            cx * tile + tile * 0.55,
            cy * tile - tile * 0.9,
            cx * tile + tile * 0.55,
            cy * tile - tile * 0.35,
            cx * tile + tile * 0.1,
            cy * tile - tile * 0.6,
            fill="#E34343",
            outline="#330C0C",
        )
        self.canvas.tag_lower(flag)
        self.canvas.tag_lower(pole)
        self.canvas.tag_lower(pennant)

    def _spawn_ball(self) -> None:
        tile = self.TILE_SIZE
        cx = self.ball_position[0] * tile
        cy = self.ball_position[1] * tile
        if self.ball_shadow is not None:
            self.canvas.delete(self.ball_shadow)
        if self.ball_sprite is not None:
            self.canvas.delete(self.ball_sprite)
        self.ball_shadow = self.canvas.create_oval(
            cx - tile * 0.42,
            cy - tile * 0.18,
            cx + tile * 0.42,
            cy + tile * 0.18,
            fill="",
            outline="#0B4747",
            dash=(4, 2),
        )
        self.ball_sprite = self.canvas.create_oval(
            cx - tile * 0.3,
            cy - tile * 0.3,
            cx + tile * 0.3,
            cy + tile * 0.3,
            fill="#FFFFFF",
            outline="#CFCFCF",
        )
        self.canvas.tag_raise(self.ball_sprite)
        self._update_aim_indicator()

    def _reposition_ball_sprite(self) -> None:
        if self.ball_sprite is None:
            return
        tile = self.TILE_SIZE
        cx = self.ball_position[0] * tile
        cy = self.ball_position[1] * tile
        if self.ball_shadow is not None:
            self.canvas.coords(
                self.ball_shadow,
                cx - tile * 0.42,
                cy - tile * 0.18,
                cx + tile * 0.42,
                cy + tile * 0.18,
            )
        self.canvas.coords(
            self.ball_sprite,
            cx - tile * 0.3,
            cy - tile * 0.3,
            cx + tile * 0.3,
            cy + tile * 0.3,
        )
        self._update_aim_indicator()

    def _ensure_valid_club(self) -> None:
        available = self._available_club_indices()
        if self.current_club_idx not in available:
            self.current_club_idx = available[0]

    def _available_club_indices(self) -> List[int]:
        if self._force_putter():
            return [len(self.clubs) - 1]
        options: List[int] = []
        for idx, club in enumerate(self.clubs):
            if club.for_putting:
                continue
            if self.lie == "sand" and club.base_distance > 170:
                continue
            options.append(idx)
        return options or [len(self.clubs) - 2]

    def _force_putter(self) -> bool:
        return (
            self.lie == "green"
            and distance(self.ball_position, (self.hole.cup[0] + 0.5, self.hole.cup[1] + 0.5))
            <= GREEN_RANGE_YARDS
        )

    def _current_club(self) -> Club:
        return self.clubs[self.current_club_idx]

    def _update_hud(self) -> None:
        hole_no = self.hole_index + 1
        total_holes = len(self.course)
        self.hud_var.set(
            f"{self.hole.name}   Par {self.hole.par}   {self.hole.yardage} yds   Wind {self.wind_string}"
        )
        running_strokes = self.completed_strokes + self.hole_strokes
        self.info_var.set(
            f"Hole {hole_no}/{total_holes}   Strokes: {running_strokes}    Total: {format_score(self.total_relative)}"
        )
        club = self._current_club()
        to_pin = distance(self.ball_position, (self.hole.cup[0] + 0.5, self.hole.cup[1] + 0.5))
        self.detail_var.set(
            f"Aim {self.aim_degrees:+}°   Lie {self.lie.capitalize():<10} Dist {to_pin:>5.1f} yds"
        )
        roll_str = f"roll {club.roll:.0f} yds" if not club.for_putting else "roll 0"
        self.club_info_var.set(
            f"Club {club.name:<12} carry {club.base_distance:.0f} yds | {roll_str} | spray ±{club.accuracy:.1f}°"
        )
        self.controls_var.set("Space swing | [,] club | ←/→ aim | Enter next | Esc quit")

    def _refresh_scoreboard(self) -> None:
        lines = ["Front Nine Scorecard", "Hole Par Str  +/-"]
        for idx, hole in enumerate(self.course, start=1):
            if idx <= len(self.scorecard):
                strokes, rel = self.scorecard[idx - 1]
                str_strokes = f"{strokes:>3}"
                rel_str = f"{format_score(rel):>3}"
            else:
                str_strokes = " --"
                rel_str = " --"
            lines.append(f" {idx:>2}   {hole.par:>2} {str_strokes} {rel_str}")
        self.scoreboard_var.set("\n".join(lines))

    def _update_meter_visual(self) -> None:
        self.power_canvas.delete("all")
        width = int(float(self.power_canvas.cget("width")))
        height = int(float(self.power_canvas.cget("height")))
        min_power, max_power = self._power_limits()
        span = max_power - min_power
        normalized = (self.power_value - min_power) / float(span or 1)
        bar_width = width * normalized
        fill = "#41EFEF" if not self._current_club().for_putting else "#F2D03C"
        self.power_canvas.create_rectangle(0, 0, width, height, fill="#041818", outline="")
        self.power_canvas.create_rectangle(0, 0, bar_width, height, fill=fill, outline="")
        self.power_canvas.create_rectangle(0, 0, width, height, outline="#0A4545")
        self.power_canvas.create_text(width - 6, height / 2, anchor="e", fill="#9CEBEA",
                                      font=("IBM Plex Mono", 10), text=f"Power {int(self.power_value)}")

    def _power_limits(self) -> Tuple[int, int]:
        return POWER_LIMITS["putt"] if self._current_club().for_putting else POWER_LIMITS["full"]

    def _update_aim_indicator(self) -> None:
        if self.ball_sprite is None:
            return
        tile = self.TILE_SIZE
        bx = self.ball_position[0] * tile
        by = self.ball_position[1] * tile
        cup_center = (self.hole.cup[0] + 0.5, self.hole.cup[1] + 0.5)
        target_angle = angle_to(cup_center, self.ball_position)
        aim_angle = target_angle + math.radians(self.aim_degrees)
        club = self._current_club()
        length_multiplier = clamp(club.base_distance / 20.0, 4.0, 16.0)
        length = tile * length_multiplier * (0.55 if not club.for_putting else 0.35)
        ex = bx + math.cos(aim_angle) * length
        ey = by + math.sin(aim_angle) * length

        target_length = tile * clamp(distance(self.ball_position, cup_center) / 6.0, 3.0, 14.0)
        tx = bx + math.cos(target_angle) * target_length
        ty = by + math.sin(target_angle) * target_length

        if self.target_indicator is None:
            self.target_indicator = self.canvas.create_line(bx, by, tx, ty,
                                                            fill="#3C74F2", dash=(4, 3), width=2)
            self.canvas.tag_lower(self.target_indicator)
        else:
            self.canvas.coords(self.target_indicator, bx, by, tx, ty)

        if self.aim_indicator is None:
            self.aim_indicator = self.canvas.create_line(bx, by, ex, ey,
                                                         fill="#F26B38", width=2, arrow=tk.LAST)
        else:
            self.canvas.coords(self.aim_indicator, bx, by, ex, ey)
        self.canvas.tag_lower(self.target_indicator)
        self.canvas.tag_raise(self.aim_indicator)
        if self.ball_sprite is not None:
            self.canvas.tag_raise(self.ball_sprite)

    # -- Input handlers ------------------------------------------------------

    def on_left(self, _event: tk.Event) -> None:
        if self.power_meter_active or self.awaiting_next or self.animating_shot:
            return
        self.aim_degrees = int(clamp(self.aim_degrees - 1, -MAX_AIM_DEGREES, MAX_AIM_DEGREES))
        self._update_hud()
        self._update_aim_indicator()

    def on_right(self, _event: tk.Event) -> None:
        if self.power_meter_active or self.awaiting_next or self.animating_shot:
            return
        self.aim_degrees = int(clamp(self.aim_degrees + 1, -MAX_AIM_DEGREES, MAX_AIM_DEGREES))
        self._update_hud()
        self._update_aim_indicator()

    def on_prev_club(self, _event: tk.Event) -> None:
        if self.power_meter_active or self.awaiting_next or self.animating_shot:
            return
        available = self._available_club_indices()
        if len(available) == 1:
            return
        try:
            idx = available.index(self.current_club_idx)
        except ValueError:
            idx = 0
        self.current_club_idx = available[(idx - 1) % len(available)]
        self._update_hud()
        self._update_meter_visual()
        self._update_aim_indicator()

    def on_next_club(self, _event: tk.Event) -> None:
        if self.power_meter_active or self.awaiting_next or self.animating_shot:
            return
        available = self._available_club_indices()
        if len(available) == 1:
            return
        try:
            idx = available.index(self.current_club_idx)
        except ValueError:
            idx = 0
        self.current_club_idx = available[(idx + 1) % len(available)]
        self._update_hud()
        self._update_meter_visual()
        self._update_aim_indicator()

    def on_space(self, _event: tk.Event) -> None:
        if self.awaiting_next or self.animating_shot:
            return
        if not self.power_meter_active:
            self._start_power_meter()
        else:
            self._fire_shot()

    def on_return(self, _event: tk.Event) -> None:
        if not self.awaiting_next or self.animating_shot:
            return
        if self.hole_index + 1 < len(self.course):
            self.load_hole(self.hole_index + 1)
        else:
            summary = (f"Front nine complete!\n\nTotal strokes: {self.completed_strokes}\n"
                       f"Score: {format_score(self.total_relative)}")
            if messagebox:
                messagebox.showinfo("Round Complete", summary)
            else:
                self.status_var.set(summary)
            self.awaiting_next = False
            self.next_prompt_var.set("")

    # -- Power meter ---------------------------------------------------------

    def _start_power_meter(self) -> None:
        self.power_meter_active = True
        min_power, _ = self._power_limits()
        self.power_value = min_power
        self.power_direction = 1
        self.status_var.set("Swing meter cycling. Tap space to strike.")
        self._animate_power_meter()

    def _animate_power_meter(self) -> None:
        if not self.power_meter_active:
            return
        min_power, max_power = self._power_limits()
        step = 3 if not self._current_club().for_putting else 4
        self.power_value += step * self.power_direction
        if self.power_value >= max_power:
            self.power_value = max_power
            self.power_direction = -1
        elif self.power_value <= min_power:
            self.power_value = min_power
            self.power_direction = 1
        self._update_meter_visual()
        self.root.after(55, self._animate_power_meter)

    def _fire_shot(self) -> None:
        self.power_meter_active = False
        previous_position = self.ball_position
        club = self._current_club()
        self.animating_shot = True
        result = simulate_shot(
            ball=self.ball_position,
            hole=self.hole,
            club=club,
            power=int(self.power_value),
            lie=self.lie,
            aim_adjust=self.aim_degrees,
            rng=self.rng,
        )
        self._apply_shot_result(result, previous_position)

    # -- Shot resolution -----------------------------------------------------

    def _apply_shot_result(self, result: ShotResult, start_position: Tuple[float, float]) -> None:
        self.hole_strokes += result.strokes
        self.status_var.set(result.message)

        if result.penalty:
            summary = f"Carry {result.carry:.0f}y | Wind drift {result.wind_drift:.1f}y | +1 penalty"
            self.shot_summary_var.set(summary)
            self.last_message = result.message
            self.animating_shot = False
            self._ensure_valid_club()
            self._update_hud()
            return

        summary = (
            f"Carry {result.carry:.0f}y | Roll {result.roll:.0f}y | Wind drift {result.wind_drift:.1f}y"
            if not self._current_club().for_putting
            else f"Putt {result.total:.1f}y"
        )
        self.shot_summary_var.set(summary)
        self.last_message = result.message
        self._animate_ball_path(start_position, result)

    def _animate_ball_path(self, start: Tuple[float, float], result: ShotResult) -> None:
        end = result.position
        tile = self.TILE_SIZE
        dist_px = math.hypot((end[0] - start[0]) * tile, (end[1] - start[1]) * tile)
        steps = max(10, min(70, int(dist_px / (tile * 0.5))))
        path = [
            (
                start[0] + (end[0] - start[0]) * (i / steps),
                start[1] + (end[1] - start[1]) * (i / steps),
            )
            for i in range(1, steps + 1)
        ]

        def advance(idx: int) -> None:
            if idx >= len(path):
                finish()
                return
            self.ball_position = path[idx]
            self._reposition_ball_sprite()
            self.root.after(25, lambda: advance(idx + 1))

        def finish() -> None:
            self.ball_position = end
            self._reposition_ball_sprite()
            self._draw_shot_tracer(start, end, result.holed)

            if result.holed:
                self.lie = "cup"
                hole_score = self.hole_strokes - self.hole.par
                self.completed_strokes += self.hole_strokes
                self.total_relative += hole_score
                self.scorecard.append((self.hole_strokes, hole_score))
                self.last_message = (
                    f"Hole {self.hole_index + 1} finished in {self.hole_strokes} strokes. "
                    f"Score {format_score(hole_score)} ({format_score(self.total_relative)})"
                )
                self.status_var.set(self.last_message)
                self.next_prompt_var.set("Press Enter to continue to the next tee.")
                self.awaiting_next = True
            else:
                self.lie = "green" if result.lie == "cup" else result.lie
                self.awaiting_next = False
                self.next_prompt_var.set("")

            self.animating_shot = False
            self._ensure_valid_club()
            self._update_hud()
            self._refresh_scoreboard()

        advance(0)

    def _draw_shot_tracer(self, start: Tuple[float, float], end: Tuple[float, float], holed: bool) -> None:
        tile = self.TILE_SIZE
        sx, sy = start[0] * tile, start[1] * tile
        ex, ey = end[0] * tile, end[1] * tile
        colour = "#F29431" if not holed else "#F25F5F"
        item = self.canvas.create_line(sx, sy, ex, ey, fill=colour, width=2)
        self.tracer_items.append(item)
        if len(self.tracer_items) > 6:
            oldest = self.tracer_items.pop(0)
            self.canvas.delete(oldest)
        self.canvas.tag_lower(item)

    # -- Main loop -----------------------------------------------------------

    def run(self) -> None:
        splash = textwrap.dedent(
            """
             ____   ____   _____       ______        ________       _______
            |  _ \ / __ \ / ____|     |  ____|      |  ____\ \     / /  __ \
            | |_) | |  | | |  __ _____| |__   _ __  | |__   \ \   / /| |  | |
            |  _ <| |  | | | |_ |______|  __| | '_ \ |  __|   \ \ / / | |  | |
            | |_) | |__| | |__| |      | |____| | | || |____   \ V /  | |__| |
            |____/ \____/ \_____|      |______|_| |_||______|   \_/    \____/

            DOS Golf Pro Tour '90
            Aim with ←/→, cycle clubs with [, ], and tap space to run the meter then strike.
            Watch the shot tracer and summary readout for carry/roll info. Enter moves to the next tee.
            """
        )
        print(splash)
        self.status_var.set("Tap space to start the swing meter when ready.")
        self.root.mainloop()


# --- Course data -----------------------------------------------------------


def build_layout(layout_str: str) -> List[str]:
    rows = [row.rstrip("\n") for row in textwrap.dedent(layout_str).strip("\n").split("\n")]
    width = max(len(row) for row in rows)
    return [row.ljust(width, " ") for row in rows]


def build_course() -> List[Hole]:
    return [
        Hole(
            name="Sunset Links #1",
            par=4,
            yardage=360,
            layout=build_layout(
                """
                ............................................................
                ......................^^^^^^^...............................
                ..........~~~~~~......^^^^^^^..............^^^^............
                ..........~~~~~~......=====^^..............^^^^............
                ..........~~~~~~......=====^^..............^^^^............
                ....=====.~~~~~~......=====^^..............====............
                ....=====.~~~~~~......=====^^..............====............
                ....=====.~~~~~~......=====^^..............====............
                ....=====.~~~~~~......=====^^..............====............
                ....T===.~~~~~~......=====^^..............====............
                ....=====.~~~~~~......=====^^..............====............
                ....=====.~~~~~~......=====^^..............====............
                ....=====.~~~~~~......=====^^..............====............
                ....=====.~~~~~~......=====^^..............====............
                ....=====.~~~~~~......=====^^..............====............
                ....=====.~~~~~~......=====^^..............====............
                ....=====.~~~~~~......===========...........GGGGGGGGGG.....
                ....=====.~~~~~~......===========...........GGGGGHGGGG.....
                .............................................GGGGGGGGG.....
                .............................................GGGGGGGGG.....
                """
            ),
            tee=(5, 9),
            cup=(50, 17),
            wind_speed=7,
            wind_direction=285,
        ),
        Hole(
            name="Lakeside Bend #2",
            par=5,
            yardage=520,
            layout=build_layout(
                """
                ............................................................
                ............................................................
                ......^^^^^^^^^^^^^^^^^..........................~~~~~~.....
                ......^^^^^^^^^^^^^^^^^.........................~~~~~~~.....
                ......====T===========.........................~~~~~~~.....
                ......================.........................~~~~~~~.....
                ......================.........................~~~~~~~.....
                ......================.............SSSSS.......~~~~~~~.....
                ......================............SSSSSSS......~~~~~~~.....
                ......================............SSSSSSS......~~~~~~~.....
                ......================............SSSSSSS......~~~~~~~.....
                ......================............SSSSSSS......~~~~~~~.....
                ......================............SSSSSSS..................
                ......================............SSSSSSS..................
                ......================............SSSSSSS..................
                ......================............SSSSSSS..................
                ......================.............SSSSS..........GGGGGGG..
                ......================..........................GGGGHGGG..
                ................................................GGGGGGGG..
                ................................................GGGGGGGG..
                """
            ),
            tee=(12, 4),
            cup=(53, 17),
            wind_speed=11,
            wind_direction=90,
        ),
        Hole(
            name="Prairie Stretch #3",
            par=3,
            yardage=165,
            layout=build_layout(
                """
                ............................................................
                ............................................................
                .......................^^^^^^^..............................
                .......................^^^^^^^..............................
                .......................^^^^^^^..............................
                .......................^^^^^^^..............................
                .................TTT...=====...............................
                ................=====..=====...............................
                ...............======..=====...............................
                ..............=======..=====...............................
                .............========..=====...............................
                ..............=======..=====.............GGGGGGGGGG........
                ...............======..=====.............GGGGGGGGGG........
                ................=====..=====.............GGGGHGGGGG........
                .................TTT...=====.............GGGGGGGGGG........
                .......................^^^^^^^..............................
                .......................^^^^^^^..............................
                .......................^^^^^^^..............................
                ............................................................
                ............................................................
                """
            ),
            tee=(25, 6),
            cup=(48, 12),
            wind_speed=4,
            wind_direction=45,
        ),
        Hole(
            name="Quarry Run #4",
            par=4,
            yardage=400,
            layout=build_layout(
                """
                ............................................................
                .....~~~~~~.................................................
                .....~~~~~~.............^^^^^^^^^^^^^^^^...................
                .....~~~~~~.............^^^^^^^^^^^^^^^^...................
                .....~~~~~~.............====T========.......................
                .....~~~~~~.............============.......................
                .....~~~~~~.............============.......................
                .....~~~~~~.............============.......................
                .....~~~~~~.............============.......................
                .....~~~~~~.............============.......................
                .....~~~~~~.............============.......................
                .....~~~~~~.............============.......................
                .....~~~~~~.............============.......................
                .....~~~~~~.............============.......................
                .....~~~~~~.............============.......................
                .....~~~~~~.............============.............GGGGGGGG...
                .........................^^^^^^^^^^^^^^^^........GGGHHGGG...
                .........................^^^^^^^^^^^^^^^^........GGGGGGGG...
                ............................................................
                ............................................................
                """
            ),
            tee=(34, 4),
            cup=(52, 16),
            wind_speed=9,
            wind_direction=200,
        ),
        Hole(
            name="Twin Pines #5",
            par=4,
            yardage=380,
            layout=build_layout(
                """
                ............................................................
                ....^^^^^^^....^^^^^^^.....................................
                ....^^^^^^^....^^^^^^^.....................................
                ....====T==....====........................................
                ....=======....====..............~~~~~~....................
                ....=======....====..............~~~~~~....................
                ....=======....====..............~~~~~~....................
                ....=======....====..............~~~~~~....................
                ....=======....====..............~~~~~~....................
                ....=======....====..............~~~~~~....................
                ....=======....====..............~~~~~~....................
                ....=======....====..............~~~~~~....................
                ....=======....====..............~~~~~~....................
                ....=======....====..............~~~~~~....................
                ....=======....====..............~~~~~~....................
                ....=======....====..............~~~~~~....................
                .........................GGGGGGGGGGGG......................
                .........................GGGGHGGGGGG.......................
                .........................GGGGGGGGGGG.......................
                ............................................................
                """
            ),
            tee=(10, 3),
            cup=(45, 17),
            wind_speed=6,
            wind_direction=315,
        ),
        Hole(
            name="Canal Carry #6",
            par=3,
            yardage=188,
            layout=build_layout(
                """
                ............................................................
                ............................................................
                .................~~~~~~.....................................
                .................~~~~~~.....................................
                .................~~~~~~.....................................
                .................~~~~~~.....................................
                .........TTT.....~~~~~~.....................................
                .............=====~~~~~~....................................
                ............======~~~~~~....................................
                ...........=======~~~~~~....................................
                ..........========~~~~~~....................................
                .........=========~~~~~~....................................
                ..........========~~~~~~....................................
                ...........=======~~~~~~....................................
                ............======~~~~~~....................................
                .............=====~~~~~~..............GGGGGGGG..............
                ..................~~~~~~.............GGGGHGGG..............
                ..................~~~~~~.............GGGGGGGG..............
                ............................................................
                ............................................................
                """
            ),
            tee=(9, 6),
            cup=(46, 16),
            wind_speed=13,
            wind_direction=250,
        ),
        Hole(
            name="Railway Dogleg #7",
            par=5,
            yardage=525,
            layout=build_layout(
                """
                ............................................................
                ..............................^^^^^^^^^^^^^^^^^^^^^^^^^.....
                ..........T======............^^^^^^^^^^^^^^^^^^^^^^^^^.....
                ..........=======............====..........................
                ..........=======............====..........................
                ..........=======............====..........................
                ..........=======............====..........................
                ..........=======............====..........................
                ..........=======............====..........................
                ..........=======............====..........................
                ..........=======............====..........................
                ..........=======............====..........................
                ..........=======............====..........................
                ..........=======............====............GGGGGGGGGG....
                ..........=======............====............GGGGHGGGGG....
                ..........=======............====............GGGGGGGGGG....
                ..........=======............====..........................
                ..........=======............====..........................
                ............................................................
                ............................................................
                """
            ),
            tee=(10, 2),
            cup=(52, 14),
            wind_speed=5,
            wind_direction=135,
        ),
        Hole(
            name="Seaside Bluff #8",
            par=4,
            yardage=408,
            layout=build_layout(
                """
                ............................................................
                ....~~~~~~..................................................
                ....~~~~~~..................................................
                ....~~~~~~..................................................
                ....~~~~~~..............^^^^^^^^^^^^^^^^...................
                ....~~~~~~..............^^^^^^^^^^^^^^^^...................
                ....~~~~~~..............====T=======.......................
                ....~~~~~~..............===========.......................
                ....~~~~~~..............===========.......................
                ....~~~~~~..............===========.......................
                ....~~~~~~..............===========.......................
                ....~~~~~~..............===========.......................
                ....~~~~~~..............===========............GGGGGGGGG...
                ....~~~~~~..............===========............GGGGHGGGG...
                ....~~~~~~..............===========............GGGGGGGGG...
                ....~~~~~~..............===========............GGGGGGGGG...
                ....~~~~~~..............===========............GGGGGGGGG...
                ....~~~~~~..................................................
                ............................................................
                ............................................................
                """
            ),
            tee=(33, 6),
            cup=(52, 13),
            wind_speed=14,
            wind_direction=20,
        ),
        Hole(
            name="Old Orchard #9",
            par=4,
            yardage=370,
            layout=build_layout(
                """
                ............................................................
                ..^^^^^^^......^^^^^^^......^^^^^^^........................
                ..^^^^^^^......^^^^^^^......^^^^^^^........................
                ..====T==......====.............====.......................
                ..=======......====.............====.......................
                ..=======......====.............====.......................
                ..=======......====.............====.......................
                ..=======......====.............====.......................
                ..=======......====.............====.......................
                ..=======......====.............====.......................
                ..=======......====.............====.......................
                ..=======......====.............====.......................
                ..=======......====.............====.......................
                ..=======......====.............====.......................
                ..=======......====.............====.......................
                ..=======......====.............====.......................
                .........................GGGGGGGGGGGG......................
                .........................GGGGHGGGGGG.......................
                .........................GGGGGGGGGGG.......................
                ............................................................
                """
            ),
            tee=(8, 3),
            cup=(46, 17),
            wind_speed=3,
            wind_direction=270,
        ),
    ]


# --- Entry point -----------------------------------------------------------


def main() -> None:
    clubs = [
        Club("Driver", 235, accuracy=4.1, roll=22),
        Club("3 Wood", 215, accuracy=3.9, roll=16),
        Club("5 Wood", 195, accuracy=3.6, roll=12),
        Club("4 Iron", 180, accuracy=3.2, roll=9),
        Club("5 Iron", 168, accuracy=3.0, roll=7),
        Club("6 Iron", 156, accuracy=2.8, roll=6),
        Club("7 Iron", 145, accuracy=2.6, roll=5),
        Club("8 Iron", 132, accuracy=2.5, roll=4),
        Club("9 Iron", 120, accuracy=2.3, roll=3),
        Club("Pitch Wedge", 105, accuracy=2.0, roll=2),
        Club("Sand Wedge", 88, accuracy=1.9, roll=1.2),
        Club("Putter", 75, accuracy=1.0, roll=0, for_putting=True),
    ]

    course = build_course()
    GameApp(course, clubs).run()


if __name__ == "__main__":
    main()
