#!/usr/bin/env python3
"""
DOS Golf Pro Tour '90 - v2
Inspired by Accolade's Mean 18 (1986) front-nine experience with a suitcase-PC vibe.
Features a 3-click swing meter, overhead course map, faux-perspective flyover panel,
animated ball flight, shot breakdowns, and running tournament scoreboard.
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
except ImportError:  # pragma: no cover - messagebox unavailable in some minimal envs
    messagebox = None

# --- Constants --------------------------------------------------------------

CELL_YARDS = 5.0  # tiles represent ~5 yards on the ground
FLAG_CAPTURE_RADIUS = 1.6  # yards; anything inside drops
GREEN_RANGE_YARDS = 34.0  # force-putter when on green inside this
MAX_PLAYER_OFFSET = 3.0  # degrees player can influence via 3rd click

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

LIE_SPIN_PENALTY = {
    "tee": 1.0,
    "fairway": 1.0,
    "rough": 1.08,
    "sand": 1.18,
    "green": 0.95,
}

SHOT_MESSAGES = {
    "tee": "Teed up nicely.",
    "fairway": "Ball finds the short grass.",
    "rough": "It hops into the rough.",
    "sand": "Splash of sand – bunker duty.",
    "green": "You're dancing on the green!",
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
    "T": "#197878",
    "=": "#2FB553",
    "-": "#2FB553",
    ".": "#0F4F2C",
    "^": "#0A3A1F",
    "#": "#0A3A1F",
    "S": "#C8A45C",
    "G": "#7BFA7B",
    "H": "#F7ED5F",
    "~": "#194E98",
    " ": "#021414",
}

# --- Data models ------------------------------------------------------------


@dataclass(frozen=True)
class Club:
    name: str
    base_distance: float  # yards
    accuracy: float  # base spray standard deviation in degrees
    roll: float  # yards of roll out after carry
    for_putting: bool = False


@dataclass(frozen=True)
class Hole:
    name: str
    par: int
    yardage: int
    layout: Sequence[str]
    tee: Tuple[int, int]
    cup: Tuple[int, int]
    wind_speed: int
    wind_direction: int  # 0=E, 90=S, 180=W, 270=N

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
    carry: float
    roll: float
    wind_drift: float
    total: float
    penalty: bool


# --- Geometry helpers -------------------------------------------------------


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
    drift = wind_scale * club_factor * rng.uniform(0.35, 0.9)
    direction_rad = math.radians(hole.wind_direction)
    return math.cos(direction_rad) * drift, math.sin(direction_rad) * drift


def simulate_shot(
    ball: Tuple[float, float],
    hole: Hole,
    club: Club,
    power: int,
    lie: str,
    aim_adjust: float,
    player_offset: float,
    rng: random.Random,
) -> ShotResult:
    cup_center = (hole.cup[0] + 0.5, hole.cup[1] + 0.5)
    base_angle = angle_to(cup_center, ball)
    intended = base_angle + math.radians(aim_adjust + player_offset)
    spray_sigma = max(0.25, club.accuracy * LIE_SPIN_PENALTY.get(lie, 1.0) * 0.32)
    spray = rng.gauss(0.0, math.radians(spray_sigma))
    shot_angle = intended + spray

    lie_effect = LIE_EFFECTS.get(lie, 0.8)
    wind_shift_cells = (0.0, 0.0)

    if club.for_putting:
        base_feet = club.base_distance * (power / 100.0)
        noisy_feet = clamp(base_feet + rng.gauss(0, base_feet * 0.08), 0, 96)
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
        return ShotResult(ball, lie, False, 2, "Splash! Water hazard.", carry_yards, roll_yards, wind_yards,
                          carry_yards + roll_yards, True)
    if tile == " ":
        return ShotResult(ball, lie, False, 2, "Out of bounds. Stroke and distance.", carry_yards, roll_yards,
                          wind_yards, carry_yards + roll_yards, True)

    new_position = (new_x, new_y)
    segment_dist = segment_distance_to_point(ball, new_position, cup_center)

    if tile == "H" or segment_dist * CELL_YARDS <= FLAG_CAPTURE_RADIUS:
        return ShotResult(cup_center, "cup", True, 1, "Tin cup clank – it's in!",
                          carry_yards, roll_yards, wind_yards, carry_yards + roll_yards, False)

    new_lie = lie_for_tile(tile)
    new_lie = "green" if tile in {"G", "H"} else new_lie
    return ShotResult(new_position, new_lie, False, 1,
                      SHOT_MESSAGES.get(new_lie, "Ball comes to rest."),
                      carry_yards, roll_yards, wind_yards, carry_yards + roll_yards, False)


# --- Game -------------------------------------------------------------------


class GameApp:
    TILE_SIZE = 16
    BG_COLOR = "#041818"
    PANEL_BG = "#073434"
    PANEL_FG = "#8AF2F2"
    STATUS_FG = "#F4E48C"
    LEGEND_FG = "#5BE1C4"

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
        self.scorecard: List[Tuple[int, int]] = []

        self.current_club_idx = 0
        self.aim_degrees = 0
        self.player_offset = 0.0
        self.target_percent: int | None = None

        self.swing_stage = "idle"  # idle -> power -> tempo
        self.meter_value = 0.0
        self.meter_direction = 1
        self.selected_power = 0
        self.selected_tempo = 50

        self.awaiting_next = False
        self.animating_shot = False

        self.root = tk.Tk()
        self.root.title("DOS Golf Pro Tour '90")
        self.root.configure(bg=self.BG_COLOR)
        self.root.resizable(False, False)

        self._build_widgets()
        self._bind_keys()

        self.wind_string = format_wind(self.hole.wind_speed, self.hole.wind_direction)
        self.last_message = "Welcome to the tour."

        self.tracer_items: List[int] = []
        self.prediction_marker_ids: List[int] = []
        self.ball_sprite: int | None = None
        self.ball_shadow: int | None = None
        self.aim_indicator: int | None = None
        self.target_indicator: int | None = None

        self.load_hole(0)

    def _play_sound(self, kind: str) -> None:
        try:
            bell = self.root.bell
        except Exception:
            return
        if kind == "start":
            bell()
        elif kind == "impact":
            self.root.after(0, bell)
        elif kind == "holed":
            for idx in range(3):
                self.root.after(80 * idx, bell)
        elif kind == "penalty":
            for idx in range(2):
                self.root.after(120 * idx, bell)

    # -- UI ------------------------------------------------------------------

    def _build_widgets(self) -> None:
        header = tk.Frame(self.root, bg=self.PANEL_BG, bd=2, relief="ridge")
        header.pack(fill="x", padx=10, pady=(10, 4))

        self.banner_var = tk.StringVar()
        self.score_var = tk.StringVar()
        self.detail_var = tk.StringVar()
        self.club_var = tk.StringVar()

        tk.Label(header, textvariable=self.banner_var, fg=self.PANEL_FG, bg=self.PANEL_BG,
                 font=("IBM Plex Mono", 12, "bold"), anchor="w", padx=6).pack(fill="x")
        tk.Label(header, textvariable=self.score_var, fg=self.PANEL_FG, bg=self.PANEL_BG,
                 font=("IBM Plex Mono", 10), anchor="w", padx=6).pack(fill="x")
        tk.Label(header, textvariable=self.detail_var, fg=self.PANEL_FG, bg=self.PANEL_BG,
                 font=("IBM Plex Mono", 10), anchor="w", padx=6).pack(fill="x")
        tk.Label(header, textvariable=self.club_var, fg=self.PANEL_FG, bg=self.PANEL_BG,
                 font=("IBM Plex Mono", 10), anchor="w", padx=6).pack(fill="x")

        main = tk.Frame(self.root, bg=self.BG_COLOR)
        main.pack(padx=10, pady=4)

        width = self.hole.width * self.TILE_SIZE
        height = self.hole.height * self.TILE_SIZE

        self.map_canvas = tk.Canvas(main, width=width, height=height, bg="#001010",
                                    highlightthickness=1, highlightbackground="#105050")
        self.map_canvas.grid(row=0, column=0, rowspan=2, padx=(0, 8))

        self.perspective_canvas = tk.Canvas(main, width=320, height=180, bg="#081010",
                                            highlightthickness=1, highlightbackground="#105050")
        self.perspective_canvas.grid(row=0, column=1, sticky="n")

        legend_frame = tk.Frame(main, bg=self.PANEL_BG, bd=1, relief="ridge")
        legend_frame.grid(row=1, column=1, sticky="nsew")
        legend_text = (
            "Controls:\n"
            "  SPACE → start / set power / set tempo\n"
            "  ↑/↓ → adjust camera arc\n"
            "  ←/→ → aim left/right\n"
            "  [, ] or , . → change club\n"
            "  ENTER → next hole\n"
            "  ESC → exit"
        )
        tk.Label(legend_frame, text=legend_text, justify="left", fg=self.PANEL_FG, bg=self.PANEL_BG,
                 font=("IBM Plex Mono", 9), padx=6, pady=6).pack()

        meter_frame = tk.Frame(self.root, bg=self.BG_COLOR)
        meter_frame.pack(fill="x", padx=10)
        self.meter_canvas = tk.Canvas(meter_frame, width=width, height=28, bg="#052525",
                                      highlightthickness=1, highlightbackground="#0C3F3F")
        self.meter_canvas.pack()
        self.swing_stage_var = tk.StringVar()
        tk.Label(meter_frame, textvariable=self.swing_stage_var, fg=self.PANEL_FG, bg=self.BG_COLOR,
                 font=("IBM Plex Mono", 10), pady=4).pack()

        footer = tk.Frame(self.root, bg=self.PANEL_BG, bd=2, relief="ridge")
        footer.pack(fill="x", padx=10, pady=(4, 8))
        self.status_var = tk.StringVar()
        self.shot_summary_var = tk.StringVar()
        self.next_prompt_var = tk.StringVar()
        tk.Label(footer, textvariable=self.status_var, fg=self.STATUS_FG, bg=self.PANEL_BG,
                 font=("IBM Plex Mono", 10), anchor="w", padx=6).pack(fill="x")
        tk.Label(footer, textvariable=self.shot_summary_var, fg=self.PANEL_FG, bg=self.PANEL_BG,
                 font=("IBM Plex Mono", 10), anchor="w", padx=6).pack(fill="x")
        tk.Label(footer, textvariable=self.next_prompt_var, fg=self.LEGEND_FG, bg=self.PANEL_BG,
                 font=("IBM Plex Mono", 10), anchor="w", padx=6).pack(fill="x")

        scoreboard_frame = tk.Frame(self.root, bg=self.BG_COLOR, bd=1, relief="ridge")
        scoreboard_frame.pack(fill="x", padx=10, pady=(0, 8))
        self.scoreboard_var = tk.StringVar()
        tk.Label(scoreboard_frame, textvariable=self.scoreboard_var, fg="#84F2C8", bg=self.BG_COLOR,
                 font=("IBM Plex Mono", 10), justify="left", padx=6, pady=6).pack(fill="x")

    def _bind_keys(self) -> None:
        self.root.bind("<Left>", self.on_left)
        self.root.bind("<Right>", self.on_right)
        self.root.bind("<Up>", self.on_up)
        self.root.bind("<Down>", self.on_down)
        self.root.bind("<space>", self.on_space)
        self.root.bind("<KeyPress-bracketleft>", self.on_prev_club)
        self.root.bind("<KeyPress-bracketright>", self.on_next_club)
        self.root.bind("<KeyPress-comma>", self.on_prev_club)
        self.root.bind("<KeyPress-period>", self.on_next_club)
        self.root.bind("<Return>", self.on_return)
        self.root.bind("<Escape>", lambda _evt: self.root.destroy())

    # -- Hole setup -----------------------------------------------------------

    def load_hole(self, index: int) -> None:
        self.hole_index = index
        self.hole = self.course[index]
        self.ball_position = (self.hole.tee[0] + 0.5, self.hole.tee[1] + 0.5)
        self.lie = "tee"
        self.hole_strokes = 0
        self.aim_degrees = 0
        self.player_offset = 0.0
        self.awaiting_next = False
        self.animating_shot = False
        self.swing_stage = "idle"
        self.selected_power = 0
        self.selected_tempo = 50
        self.wind_string = format_wind(self.hole.wind_speed, self.hole.wind_direction)
        self.status_var.set("Set your opening shot.")
        self.shot_summary_var.set("")
        self.next_prompt_var.set("")

        for item in self.tracer_items:
            self.map_canvas.delete(item)
        self.tracer_items.clear()
        for item in self.prediction_marker_ids:
            self.map_canvas.delete(item)
        self.prediction_marker_ids.clear()
        if self.target_indicator is not None:
            self.target_indicator = None
        if self.aim_indicator is not None:
            self.aim_indicator = None

        self._draw_hole_map()
        self._spawn_ball()
        self._update_hud()
        self._refresh_scoreboard()
        self._update_meter_visual()
        self._render_perspective()

    def _draw_hole_map(self) -> None:
        self.map_canvas.delete("all")
        tile = self.TILE_SIZE
        for y, row in enumerate(self.hole.layout):
            for x, ch in enumerate(row):
                color = TILE_COLORS.get(ch, "#0A3A1F")
                self.map_canvas.create_rectangle(
                    x * tile,
                    y * tile,
                    (x + 1) * tile,
                    (y + 1) * tile,
                    fill=color,
                    outline="#063030",
                )
        cx, cy = self.hole.cup
        self.map_canvas.create_rectangle(
            cx * tile + tile * 0.3,
            cy * tile + tile * 0.3,
            cx * tile + tile * 0.7,
            cy * tile + tile * 0.7,
            fill="#F8F094",
            outline="#493A00",
        )
        self.map_canvas.create_polygon(
            cx * tile + tile * 0.55,
            cy * tile - tile * 0.9,
            cx * tile + tile * 0.55,
            cy * tile - tile * 0.3,
            cx * tile + tile * 0.2,
            cy * tile - tile * 0.6,
            fill="#E63C3C",
            outline="#340C0C",
        )

    def _spawn_ball(self) -> None:
        tile = self.TILE_SIZE
        cx = self.ball_position[0] * tile
        cy = self.ball_position[1] * tile
        if self.ball_shadow is not None:
            self.map_canvas.delete(self.ball_shadow)
        if self.ball_sprite is not None:
            self.map_canvas.delete(self.ball_sprite)
        self.ball_shadow = self.map_canvas.create_oval(
            cx - tile * 0.4,
            cy - tile * 0.18,
            cx + tile * 0.4,
            cy + tile * 0.18,
            outline="#0B4747",
            dash=(4, 2),
        )
        self.ball_sprite = self.map_canvas.create_oval(
            cx - tile * 0.3,
            cy - tile * 0.3,
            cx + tile * 0.3,
            cy + tile * 0.3,
            fill="#FFFFFF",
            outline="#D0D0D0",
        )
        self._update_aim_indicator()

    def _reposition_ball_sprite(self) -> None:
        if self.ball_sprite is None:
            return
        tile = self.TILE_SIZE
        cx = self.ball_position[0] * tile
        cy = self.ball_position[1] * tile
        self.map_canvas.coords(self.ball_sprite, cx - tile * 0.3, cy - tile * 0.3,
                               cx + tile * 0.3, cy + tile * 0.3)
        if self.ball_shadow is not None:
            self.map_canvas.coords(self.ball_shadow, cx - tile * 0.4, cy - tile * 0.18,
                                   cx + tile * 0.4, cy + tile * 0.18)
        self._update_aim_indicator()

    # -- HUD -----------------------------------------------------------------

    def _update_hud(self) -> None:
        hole_no = self.hole_index + 1
        total_holes = len(self.course)
        banner = f"{self.hole.name}   Par {self.hole.par}   {self.hole.yardage} yds   Wind {self.wind_string}"
        self.banner_var.set(banner)
        running_strokes = self.completed_strokes + self.hole_strokes
        self.score_var.set(f"Hole {hole_no}/{total_holes}   Strokes {running_strokes}   Total {format_score(self.total_relative)}")
        to_pin = distance(self.ball_position, (self.hole.cup[0] + 0.5, self.hole.cup[1] + 0.5))
        self.detail_var.set(f"Aim {self.aim_degrees:+}°   Lie {self.lie.capitalize():<10}   Dist {to_pin:5.1f} yds")
        club = self.clubs[self.current_club_idx]
        roll_str = f"roll {club.roll:.0f} yds" if not club.for_putting else "roll 0"
        self.target_percent = self._suggest_power_percent(club)
        target_note = f" | Target {self.target_percent}%" if self.target_percent else ""
        self.club_var.set(f"Club {club.name:<12} carry {club.base_distance:.0f} yds | {roll_str} | spray ±{club.accuracy:.1f}°{target_note}")
        advice = self._caddie_advice()
        if advice:
            self.club_var.set(self.club_var.get() + f" | Caddie: {advice}")
        self._update_prediction_overlays()

    def _refresh_scoreboard(self) -> None:
        lines = ["Front Nine Scorecard", "Hole Par Str  +/-"]
        for idx, hole in enumerate(self.course, start=1):
            if idx <= len(self.scorecard):
                strokes, rel = self.scorecard[idx - 1]
                line = f" {idx:>2}   {hole.par:>2} {strokes:>3} {format_score(rel):>3}"
            else:
                line = f" {idx:>2}   {hole.par:>2}  --  --"
            lines.append(line)
        self.scoreboard_var.set("\n".join(lines))

    def _suggest_power_percent(self, club: Club) -> int | None:
        dist = distance(self.ball_position, (self.hole.cup[0] + 0.5, self.hole.cup[1] + 0.5))
        dist = max(dist, 0.1)
        if club.for_putting:
            pct = int(round((dist / max(club.base_distance, 1.0)) * 100))
            return clamp(pct, 5, 115)
        lie_effect = LIE_EFFECTS.get(self.lie, 1.0)
        roll_factor = max(0.45, lie_effect)
        denominator = lie_effect * club.base_distance + roll_factor * club.roll
        if denominator <= 0:
            return None
        pct = int(round((dist / denominator) * 100))
        return clamp(pct, 25, 110)

    def _predict_carry(self, club: Club, percent: int | None = None) -> float:
        if percent is None:
            percent = 80
        ratio = clamp(percent, 10, 110) / 100.0
        lie_effect = LIE_EFFECTS.get(self.lie, 1.0)
        if club.for_putting:
            return club.base_distance * ratio
        roll_factor = max(0.45, lie_effect)
        carry = club.base_distance * ratio * lie_effect
        roll = club.roll * ratio * roll_factor
        return carry + roll

    def _caddie_advice(self) -> str:
        dist = distance(self.ball_position, (self.hole.cup[0] + 0.5, self.hole.cup[1] + 0.5))
        if dist < 2.0:
            return "Tap it in"
        if self._force_putter():
            putter = self.clubs[-1]
            pct = self._suggest_power_percent(putter)
            return f"Putter @{pct}%" if pct is not None else "Putter"
        candidates = self._available_club_indices()
        if not candidates:
            return ""
        def club_fit(idx: int) -> float:
            club = self.clubs[idx]
            pct = self._suggest_power_percent(club)
            if pct is None:
                return float('inf')
            return abs(dist - self._predict_carry(club, pct))
        best_idx = min(candidates, key=club_fit)
        best_club = self.clubs[best_idx]
        pct = self._suggest_power_percent(best_club)
        if pct is None:
            return best_club.name
        suffix = " (current)" if best_idx == self.current_club_idx else " (press [,] or ] to switch)"
        return f"{best_club.name} @{pct}%{suffix}"

    def _update_meter_visual(self) -> None:
        self.meter_canvas.delete("all")
        width = int(float(self.meter_canvas.cget("width")))
        height = int(float(self.meter_canvas.cget("height")))

        min_power, max_power = self._power_limits()
        span = max_power - min_power
        target_x = None
        if self.target_percent is not None and span > 0:
            normalized_target = clamp((self.target_percent - min_power) / span, 0.0, 1.0)
            target_x = width * normalized_target

        if self.swing_stage == "power":
            normalized = (self.meter_value - min_power) / float(span or 1)
            needle_x = width * normalized
            self.meter_canvas.create_rectangle(0, 0, width, height, fill="#061E1E", outline="")
            self.meter_canvas.create_rectangle(0, 0, needle_x, height, fill="#41EFEF", outline="")
            self.meter_canvas.create_rectangle(0, 0, width, height, outline="#107070")
            self.meter_canvas.create_line(needle_x, 0, needle_x, height, fill="#F4F4F4", width=2)
        elif self.swing_stage == "tempo":
            normalized = self.meter_value / 100.0
            needle_x = width * normalized
            tempo_target_x = width * 0.5
            self.meter_canvas.create_rectangle(0, 0, width, height, fill="#061E1E", outline="")
            self.meter_canvas.create_rectangle(0, 0, needle_x, height, fill="#F2D03C", outline="")
            self.meter_canvas.create_rectangle(0, 0, width, height, outline="#107070")
            self.meter_canvas.create_line(tempo_target_x, 0, tempo_target_x, height, fill="#FF8080", width=2, dash=(4, 2))
            self.meter_canvas.create_line(needle_x, 0, needle_x, height, fill="#FFFFFF", width=2)
        else:
            self.meter_canvas.create_rectangle(0, 0, width, height, fill="#061E1E", outline="#107070")

        if target_x is not None and self.swing_stage in {"idle", "power"}:
            self.meter_canvas.create_line(target_x, 0, target_x, height, fill="#7CF27C", width=2, dash=(4, 2))
            self.meter_canvas.create_text(target_x, height / 2, text=f"{self.target_percent}%",
                                          fill="#7CF27C", font=("IBM Plex Mono", 9, "bold"),
                                          anchor="n")

        stage_text = {
            "idle": (f"Target {self.target_percent}% – tap SPACE to start"
                      if self.target_percent is not None else "Swing meter idle – tap SPACE to start"),
            "power": (f"POWER: lock near {self.target_percent}% marker"
                      if self.target_percent is not None else "POWER: tap SPACE to lock"),
            "tempo": "TEMPO: keep the marker near center",
        }[self.swing_stage]
        self.swing_stage_var.set(stage_text)
        self._update_prediction_overlays()

    def _update_aim_indicator(self) -> None:
        if self.ball_sprite is None:
            return
        tile = self.TILE_SIZE
        bx = self.ball_position[0] * tile
        by = self.ball_position[1] * tile
        cup = (self.hole.cup[0] + 0.5, self.hole.cup[1] + 0.5)
        target_angle = angle_to(cup, self.ball_position)
        aim_angle = target_angle + math.radians(self.aim_degrees + self.player_offset)
        club = self.clubs[self.current_club_idx]
        length = tile * clamp(club.base_distance / 18.0, 3.0, 16.0)
        ex = bx + math.cos(aim_angle) * length
        ey = by + math.sin(aim_angle) * length
        tx = bx + math.cos(target_angle) * length
        ty = by + math.sin(target_angle) * length

        if self.target_indicator is None:
            self.target_indicator = self.map_canvas.create_line(bx, by, tx, ty,
                                                                fill="#3C74F2", width=2, dash=(4, 3))
        else:
            self.map_canvas.coords(self.target_indicator, bx, by, tx, ty)

        if self.aim_indicator is None:
            self.aim_indicator = self.map_canvas.create_line(bx, by, ex, ey,
                                                             fill="#F26B38", width=2, arrow=tk.LAST)
        else:
            self.map_canvas.coords(self.aim_indicator, bx, by, ex, ey)
        self.map_canvas.tag_lower(self.target_indicator)
        self.map_canvas.tag_raise(self.aim_indicator)
        if self.ball_sprite is not None:
            self.map_canvas.tag_raise(self.ball_sprite)
        self._update_prediction_overlays()

    def _render_perspective(self, progress: float = 0.0) -> None:
        canvas = self.perspective_canvas
        canvas.delete("all")
        w = int(float(canvas.cget("width")))
        h = int(float(canvas.cget("height")))
        horizon = h * 0.45
        canvas.create_rectangle(0, 0, w, horizon, fill="#6EC1FF", outline="")
        canvas.create_rectangle(0, horizon, w, h, fill="#226B2F", outline="")

        cup_x = w * 0.5
        canvas.create_line(cup_x, horizon, cup_x, horizon - 45, fill="#FFFFFF", width=2)
        canvas.create_polygon(cup_x, horizon - 45, cup_x, horizon - 10, cup_x - 28, horizon - 30,
                              fill="#FF4444", outline="#440000")

        ball_x = w * (0.1 + 0.8 * progress)
        ball_y = horizon + (h - horizon) * 0.2 - (progress * (1 - progress) * h * 0.45)
        canvas.create_oval(ball_x - 6, ball_y - 6, ball_x + 6, ball_y + 6,
                           fill="#FFFFFF", outline="#D0D0D0")

    # -- Input ----------------------------------------------------------------

    def on_left(self, _event: tk.Event) -> None:
        if self.awaiting_next or self.animating_shot or self.swing_stage != "idle":
            return
        self.aim_degrees = int(clamp(self.aim_degrees - 1, -12, 12))
        self._update_hud()
        self._update_aim_indicator()

    def on_right(self, _event: tk.Event) -> None:
        if self.awaiting_next or self.animating_shot or self.swing_stage != "idle":
            return
        self.aim_degrees = int(clamp(self.aim_degrees + 1, -12, 12))
        self._update_hud()
        self._update_aim_indicator()

    def on_up(self, _event: tk.Event) -> None:
        if self.awaiting_next or self.animating_shot:
            return
        self._render_perspective(progress=0.25)

    def on_down(self, _event: tk.Event) -> None:
        if self.awaiting_next or self.animating_shot:
            return
        self._render_perspective(progress=0.75)

    def on_prev_club(self, _event: tk.Event) -> None:
        if self.awaiting_next or self.animating_shot or self.swing_stage != "idle":
            return
        options = self._available_club_indices()
        if len(options) == 1:
            return
        idx = options.index(self.current_club_idx) if self.current_club_idx in options else 0
        self.current_club_idx = options[(idx - 1) % len(options)]
        self._update_hud()
        self._update_aim_indicator()

    def on_next_club(self, _event: tk.Event) -> None:
        if self.awaiting_next or self.animating_shot or self.swing_stage != "idle":
            return
        options = self._available_club_indices()
        if len(options) == 1:
            return
        idx = options.index(self.current_club_idx) if self.current_club_idx in options else 0
        self.current_club_idx = options[(idx + 1) % len(options)]
        self._update_hud()
        self._update_aim_indicator()

    def on_space(self, _event: tk.Event) -> None:
        if self.awaiting_next or self.animating_shot:
            return
        if self.swing_stage == "idle":
            self._start_power_meter()
        elif self.swing_stage == "power":
            self._lock_power()
        elif self.swing_stage == "tempo":
            self._lock_tempo()

    def on_return(self, _event: tk.Event) -> None:
        if not self.awaiting_next or self.animating_shot:
            return
        if self.hole_index + 1 < len(self.course):
            self.load_hole(self.hole_index + 1)
        else:
            total_msg = (f"Front nine complete!\n\nTotal strokes: {self.completed_strokes}\n"
                         f"Score: {format_score(self.total_relative)}")
            if messagebox:
                messagebox.showinfo("Round Complete", total_msg)
            else:
                self.status_var.set(total_msg)
            self.awaiting_next = False
            self.next_prompt_var.set("")

    # -- Swing meter ---------------------------------------------------------

    def _start_power_meter(self) -> None:
        self.swing_stage = "power"
        self.meter_direction = 1
        self.meter_value = self._power_limits()[0]
        self.player_offset = 0.0
        target = f" Aim for {self.target_percent}%" if self.target_percent is not None else ""
        self.status_var.set("Swing meter running – lock POWER with SPACE." + target)
        self._update_meter_visual()
        self._play_sound("start")
        self._tick_meter()

    def _lock_power(self) -> None:
        self.selected_power = int(self.meter_value)
        self.swing_stage = "tempo"
        self.meter_direction = 1
        self.meter_value = 0.0
        self.status_var.set("Tempo pass – keep the marker near center for accuracy")
        self._update_meter_visual()

    def _lock_tempo(self) -> None:
        self.selected_tempo = int(self.meter_value)
        self.swing_stage = "idle"
        self._update_meter_visual()
        self._fire_shot()

    def _tick_meter(self) -> None:
        if self.swing_stage == "idle":
            return
        if self.swing_stage == "power":
            min_power, max_power = self._power_limits()
            step = 2
            self.meter_value += step * self.meter_direction
            if self.meter_value >= max_power:
                self.meter_value = max_power
                self.meter_direction = -1
            elif self.meter_value <= min_power:
                self.meter_value = min_power
                self.meter_direction = 1
        elif self.swing_stage == "tempo":
            step = 3
            self.meter_value += step * self.meter_direction
            if self.meter_value >= 100:
                self.meter_value = 100
                self.meter_direction = -1
            elif self.meter_value <= 0:
                self.meter_value = 0
                self.meter_direction = 1
        self._update_meter_visual()
        self.root.after(75, self._tick_meter)

    def _power_limits(self) -> Tuple[int, int]:
        club = self.clubs[self.current_club_idx]
        return POWER_LIMITS["putt"] if club.for_putting else POWER_LIMITS["full"]

    # -- Shot handling -------------------------------------------------------

    def _available_club_indices(self) -> List[int]:
        if self._force_putter():
            return [len(self.clubs) - 1]
        indices: List[int] = []
        for idx, club in enumerate(self.clubs):
            if club.for_putting:
                continue
            if self.lie == "sand" and club.base_distance > 170:
                continue
            indices.append(idx)
        return indices or [len(self.clubs) - 2]

    def _force_putter(self) -> bool:
        return (
            self.lie == "green"
            and distance(self.ball_position, (self.hole.cup[0] + 0.5, self.hole.cup[1] + 0.5)) <= GREEN_RANGE_YARDS
        )

    def _fire_shot(self) -> None:
        club = self.clubs[self.current_club_idx]
        if club.for_putting:
            power = clamp(self.selected_power, *POWER_LIMITS["putt"])
        else:
            power = clamp(self.selected_power, *POWER_LIMITS["full"])
        tempo_ratio = clamp((self.selected_tempo - 50) / 50.0, -1.0, 1.0)
        self.player_offset = (tempo_ratio ** 3) * MAX_PLAYER_OFFSET
        self._update_aim_indicator()

        self.animating_shot = True
        result = simulate_shot(
            ball=self.ball_position,
            hole=self.hole,
            club=club,
            power=int(power),
            lie=self.lie,
            aim_adjust=self.aim_degrees,
            player_offset=self.player_offset,
            rng=self.rng,
        )
        self._resolve_shot(result)

    def _resolve_shot(self, result: ShotResult) -> None:
        self.hole_strokes += result.strokes
        summary = (f"Carry {result.carry:.0f}y | Roll {result.roll:.0f}y | Wind {result.wind_drift:.1f}y"
                   if not self.clubs[self.current_club_idx].for_putting else f"Putt {result.total:.1f}y")
        if result.penalty:
            summary += " | +1 penalty"
        tempo_note = f" | Tempo {self.selected_tempo:3d}% ({self.player_offset:+.1f}°)"
        detail = self._shot_detail(result)
        self.shot_summary_var.set(summary + tempo_note + detail)
        self.status_var.set(result.message)
        self._play_sound("impact")

        if result.penalty:
            self._play_sound("penalty")
            self.ball_position = self._find_drop_spot(self.ball_position)
            self._reposition_ball_sprite()
            self._render_perspective(progress=0.0)
            drop_tile = layout_tile(self.hole, (int(self.ball_position[0]), int(self.ball_position[1])))
            self.lie = lie_for_tile(drop_tile)
            self.animating_shot = False
            self.swing_stage = "idle"
            self.status_var.set(self.status_var.get() + " Taking a drop.")
            self._update_hud()
            return

        start_pos = self.ball_position
        end_pos = result.position
        self._animate_ball(start_pos, end_pos, result)

    def _animate_ball(self, start: Tuple[float, float], end: Tuple[float, float], result: ShotResult) -> None:
        tile = self.TILE_SIZE
        dist_px = math.hypot((end[0] - start[0]) * tile, (end[1] - start[1]) * tile)
        steps = max(14, min(80, int(dist_px / (tile * 0.45))))
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
            self._render_perspective(progress=idx / float(len(path)))
            self.root.after(25, lambda: advance(idx + 1))

        def finish() -> None:
            self.ball_position = end
            self._reposition_ball_sprite()
            self._render_perspective(progress=1.0 if result.holed else 0.4)
            self._draw_tracer(start, end, result.holed)

            if result.holed:
                self._play_sound("holed")
                self.lie = "cup"
                hole_score = self.hole_strokes - self.hole.par
                self.completed_strokes += self.hole_strokes
                self.total_relative += hole_score
                self.scorecard.append((self.hole_strokes, hole_score))
                self.status_var.set(
                    f"Hole {self.hole_index + 1} cleared in {self.hole_strokes} strokes."
                    f" Score {format_score(hole_score)} ({format_score(self.total_relative)})"
                )
                self.next_prompt_var.set("Press ENTER to walk to the next tee.")
                self.awaiting_next = True
            else:
                self.lie = result.lie
                self.awaiting_next = False
                self.next_prompt_var.set("")

            self.animating_shot = False
            self.swing_stage = "idle"
            self._update_hud()
            self._refresh_scoreboard()

        advance(0)

    def _draw_tracer(self, start: Tuple[float, float], end: Tuple[float, float], holed: bool) -> None:
        tile = self.TILE_SIZE
        sx, sy = start[0] * tile, start[1] * tile
        ex, ey = end[0] * tile, end[1] * tile
        colour = "#F49A34" if not holed else "#F55858"
        item = self.map_canvas.create_line(sx, sy, ex, ey, fill=colour, width=2)
        self.tracer_items.append(item)
        if len(self.tracer_items) > 6:
            oldest = self.tracer_items.pop(0)
            self.map_canvas.delete(oldest)

    def _current_prediction_percent(self) -> int | None:
        if self.swing_stage == "power":
            return int(self.meter_value)
        if self.swing_stage == "tempo":
            return self.selected_power if self.selected_power else None
        return self.target_percent

    def _update_prediction_overlays(self) -> None:
        for item in self.prediction_marker_ids:
            self.map_canvas.delete(item)
        self.prediction_marker_ids.clear()
        if self.target_percent is not None:
            self._draw_prediction_marker(self.target_percent, "#7CF27C", label=f"{self.target_percent}%")
        if self.swing_stage in {"power", "tempo"}:
            live_percent = self._current_prediction_percent()
            if live_percent is not None:
                color = "#F2D03C"
                label = f"{live_percent}%"
                self._draw_prediction_marker(live_percent, color, label=label)

    def _draw_prediction_marker(self, percent: int, color: str, label: str = "") -> None:
        predicted = self._predict_landing(percent)
        if predicted is None:
            return
        px, py, total = predicted
        tile = self.TILE_SIZE
        px = clamp(px, 0.0, self.hole.width - 1)
        py = clamp(py, 0.0, self.hole.height - 1)
        radius = tile * 0.8
        circle = self.map_canvas.create_oval(px * tile - radius, py * tile - radius,
                                             px * tile + radius, py * tile + radius,
                                             outline=color, dash=(3, 3))
        cross1 = self.map_canvas.create_line(px * tile - radius * 0.7, py * tile,
                                             px * tile + radius * 0.7, py * tile,
                                             fill=color)
        cross2 = self.map_canvas.create_line(px * tile, py * tile - radius * 0.7,
                                             px * tile, py * tile + radius * 0.7,
                                             fill=color)
        text_id = None
        if label or total:
            text_label = label or f"{percent}%"
            extra = f" ~{total:.0f}y" if total else ""
            text_id = self.map_canvas.create_text(px * tile, py * tile - radius - 6,
                                                  text=text_label + extra,
                                                  fill=color, font=("IBM Plex Mono", 9, "bold"))
        for item in (circle, cross1, cross2, text_id):
            if item is not None:
                self.prediction_marker_ids.append(item)

    def _predict_landing(self, percent: int) -> Tuple[float, float, float] | None:
        club = self.clubs[self.current_club_idx]
        min_power, max_power = self._power_limits()
        percent = int(clamp(percent, min_power, max_power))
        ratio = percent / 100.0
        if ratio <= 0:
            return None
        lie_effect = LIE_EFFECTS.get(self.lie, 1.0)
        if club.for_putting:
            carry = club.base_distance * ratio
            total = carry
        else:
            roll_factor = max(0.45, lie_effect)
            carry = club.base_distance * ratio * lie_effect
            roll = club.roll * ratio * roll_factor
            total = carry + roll
        if total <= 0.1:
            return None
        direction = angle_to((self.hole.cup[0] + 0.5, self.hole.cup[1] + 0.5), self.ball_position)
        direction += math.radians(self.aim_degrees + self.player_offset)
        cells = total / CELL_YARDS
        px = self.ball_position[0] + math.cos(direction) * cells
        py = self.ball_position[1] + math.sin(direction) * cells
        return px, py, total

    def _shot_detail(self, result: ShotResult) -> str:
        if result.penalty:
            return " | Drop taken"
        if result.holed:
            return " | Holed!"
        dist_left = distance(self.ball_position, (self.hole.cup[0] + 0.5, self.hole.cup[1] + 0.5))
        lie_note = f" Lie: {result.lie.capitalize()}" if result.lie not in {"cup"} else ""
        return f" | {dist_left:.1f}y remaining{lie_note}"

    def _find_drop_spot(self, origin: Tuple[float, float]) -> Tuple[float, float]:
        ox, oy = origin
        cup = (self.hole.cup[0] + 0.5, self.hole.cup[1] + 0.5)
        direction = angle_to(cup, origin)
        for step in range(1, 7):
            nx = ox + math.cos(direction) * step
            ny = oy + math.sin(direction) * step
            cell_x = int(clamp(round(nx), 0, self.hole.width - 1))
            cell_y = int(clamp(round(ny), 0, self.hole.height - 1))
            tile = layout_tile(self.hole, (cell_x, cell_y))
            if tile not in {"~", " "}:
                return (cell_x + 0.5, cell_y + 0.5)
        # fallback search around the original spot
        start_cell_x = int(clamp(round(ox - 0.5), 0, self.hole.width - 1))
        start_cell_y = int(clamp(round(oy - 0.5), 0, self.hole.height - 1))
        for radius in range(1, 5):
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    cell_x = int(clamp(start_cell_x + dx, 0, self.hole.width - 1))
                    cell_y = int(clamp(start_cell_y + dy, 0, self.hole.height - 1))
                    tile = layout_tile(self.hole, (cell_x, cell_y))
                    if tile not in {"~", " "}:
                        return (cell_x + 0.5, cell_y + 0.5)
        return origin

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

            DOS Golf Pro Tour '90  (Mean 18 Edition)
            3-click swings, CGA skyline, and tinny fairways like the early 90s.
            Tap SPACE to tee off when you're ready.
            """
        )
        print(splash)
        self.status_var.set("Tap SPACE to start the swing meter when ready.")
        self.root.mainloop()


# --- Course setup -----------------------------------------------------------


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
