"""Colours, fonts and icons taken from the forms of the original PWCT
(RPWI goal designer ``rpwi.scx``, interaction page ``runtrf.scx`` and the
components browser ``selser.scx``).  FoxPro colours are ``R,G,B``."""

import tkinter as tk
from tkinter import font as tkfont

WHITE = "#ffffff"
OLIVE = "#808000"          # "Goal Designer" title           (128,128,0)
CYAN = "#48f9e7"           # band under the header           (72,249,231)
PURPLE = "#400040"         # bar with Steps Tree / Details   (64,0,64)
GREEN = "#03e485"          # interaction page file bar       (3,228,133)
FACE = "#ece9d8"           # labels of interaction pages     (14215660)
PAGE_BG = "#eaeaea"        # interaction page background     (15395562)
TITLE_BAR = "#5f4675"      # TITLE bars of interaction pages (7685727)
NAVY = "#000080"
GRAY = "#808080"
BLACK = "#000000"
SELECT = "#316ac5"

STEP_COLORS = {"root": "#800000", "generated": "#000080", "comment": "#008000",
               "user": "#000000", "disabled": "#9a9a9a"}


def pick(root, *families):
    """The first installed font family (Impact is not on every system)."""
    installed = {f.lower() for f in tkfont.families(root)}
    for family in families:
        if family.lower() in installed:
            return family
    return families[-1]


class Fonts:
    def __init__(self, root):
        impact = pick(root, "Impact", "Haettenschweiler", "Arial Black", "DejaVu Sans Condensed",
                      "Helvetica")
        arial = pick(root, "Arial", "Liberation Sans", "DejaVu Sans", "Helvetica")
        mono = pick(root, "Courier New", "Liberation Mono", "DejaVu Sans Mono", "Courier")
        self.title = (impact, 30)
        self.title_small = (impact, 22)
        self.header = (arial, 15)
        self.big = (arial, 20)
        self.normal = (arial, 10)
        self.bold = (arial, 10, "bold")
        self.tree = (arial, 11)
        self.tree_root = (arial, 11, "bold")
        self.button = (arial, 9)
        self.code = (mono, 10)


# 16x16 icons drawn with characters, one colour per character
PALETTE = {
    ".": None, "k": "#000000", "w": "#ffffff", "g": "#1e9e2e", "G": "#7fe08a",
    "r": "#d42020", "R": "#ff8080", "b": "#1f4fbf", "B": "#8fb4ff", "y": "#f0c000",
    "Y": "#fff27a", "o": "#e07000", "s": "#9a9a9a", "S": "#d8d8d8", "p": "#400040",
    "c": "#00a0a0", "n": "#000080",
}

ICONS = {
    "new": [
        "..kkkkkkkk......",
        "..kwwwwwwkk.....",
        "..kwwwwwwkwk....",
        "..kwwwwwwkkkk...",
        "..kwwwwwwwwwk...",
        "..kwwwwwwwwwk...",
        "..kwwwwwggwwk...",
        "..kwwwwwggwwk...",
        "..kwwwggggggk...",
        "..kwwwggggggk...",
        "..kwwwwwggwwk...",
        "..kwwwwwggwwk...",
        "..kwwwwwwwwwk...",
        "..kkkkkkkkkkk...",
        "................",
        "................"],
    "delete": [
        "................",
        ".rr.........rr..",
        ".rrr.......rrr..",
        "..rrr.....rrr...",
        "...rrr...rrr....",
        "....rrr.rrr.....",
        ".....rrrrr......",
        "......rrr.......",
        ".....rrrrr......",
        "....rrr.rrr.....",
        "...rrr...rrr....",
        "..rrr.....rrr...",
        ".rrr.......rrr..",
        ".rr.........rr..",
        "................",
        "................"],
    "edit": [
        "...........kk...",
        "..........kRRk..",
        ".........kyRRk..",
        "........kyyykk..",
        ".......kyyyk....",
        "......kyyyk.....",
        ".....kyyyk......",
        "....kyyyk.......",
        "...kyyyk........",
        "..kSyyk.........",
        "..kSSk..........",
        "..kkk...........",
        "................",
        ".kkkkkkkkkkkkk..",
        "................",
        "................"],
    "up": [
        "................",
        ".......nn.......",
        "......nBBn......",
        ".....nBBBBn.....",
        "....nBBBBBBn....",
        "...nBBBBBBBBn...",
        "..nnnnBBBBnnnn..",
        ".....nBBBBn.....",
        ".....nBBBBn.....",
        ".....nBBBBn.....",
        ".....nBBBBn.....",
        ".....nBBBBn.....",
        ".....nnnnnn.....",
        "................",
        "................",
        "................"],
    "interact": [
        "................",
        "......gggg......",
        "....ggGGGGgg....",
        "...gGGGGGGGGg...",
        "..gGGGGggGGGGg..",
        "..gGGGGggGGGGg..",
        ".gGGGGGggGGGGGg.",
        ".gGGgggggggggGg.",
        ".gGGgggggggggGg.",
        ".gGGGGGggGGGGGg.",
        "..gGGGGggGGGGg..",
        "..gGGGGggGGGGg..",
        "...gGGGGGGGGg...",
        "....ggGGGGgg....",
        "......gggg......",
        "................"],
    "modify": [
        "................",
        "...oooooooooo...",
        "..oYYYYYYYYYYo..",
        "..oYkkkkkkkkYo..",
        "..oYYYYYYYYYYo..",
        "..oYkkkkkkYYYo..",
        "..oYYYYYYYYYYo..",
        "..oYkkkkkkkkYo..",
        "..oYYYYYYYYYYo..",
        "..oYkkkkkYYYYo..",
        "..oYYYYYYYYYYo..",
        "..oYYYYYYYYYYo..",
        "...oooooooooo...",
        "................",
        "................",
        "................"],
    "run": [
        "................",
        "...gg...........",
        "...gGgg.........",
        "...gGGGgg.......",
        "...gGGGGGgg.....",
        "...gGGGGGGGgg...",
        "...gGGGGGGGGGg..",
        "...gGGGGGGGGGg..",
        "...gGGGGGGGgg...",
        "...gGGGGGgg.....",
        "...gGGGgg.......",
        "...gGgg.........",
        "...gg...........",
        "................",
        "................",
        "................"],
    "stop": [
        "................",
        "................",
        "...rrrrrrrrrr...",
        "...rRRRRRRRRr...",
        "...rRRRRRRRRr...",
        "...rRRRRRRRRr...",
        "...rRRRRRRRRr...",
        "...rRRRRRRRRr...",
        "...rRRRRRRRRr...",
        "...rRRRRRRRRr...",
        "...rRRRRRRRRr...",
        "...rrrrrrrrrr...",
        "................",
        "................",
        "................",
        "................"],
    "close": [
        "................",
        ".kkkkkkkkkkkkkk.",
        ".kppppppppppppk.",
        ".kkkkkkkkkkkkkk.",
        ".kwwwwwwwwwwwwk.",
        ".kwrrwwwwwwrrwk.",
        ".kwwrrwwwwrrwwk.",
        ".kwwwrrwwrrwwwk.",
        ".kwwwwrrrrwwwwk.",
        ".kwwwwrrrrwwwwk.",
        ".kwwwrrwwrrwwwk.",
        ".kwwrrwwwwrrwwk.",
        ".kwrrwwwwwwrrwk.",
        ".kwwwwwwwwwwwwk.",
        ".kkkkkkkkkkkkkk.",
        "................"],
    "goal": [
        "................",
        ".......yy.......",
        "..y....yy....y..",
        "...y..yyyy..y...",
        "....yyYYYYyy....",
        "....yYYYYYYy....",
        "..yyYYYYYYYYyy..",
        "yyyyYYYYYYYYyyyy",
        "..yyYYYYYYYYyy..",
        "....yYYYYYYy....",
        "....yyYYYYyy....",
        "...y..yyyy..y...",
        "..y....yy....y..",
        ".......yy.......",
        "................",
        "................"],
    "step": [
        "................",
        "................",
        "................",
        "...nnnnnnnnnn...",
        "...nBBBBBBBBn...",
        "...nBwwwwwwBn...",
        "...nBwBBBBBBn...",
        "...nBwwwwwBBn...",
        "...nBwBBBBBBn...",
        "...nBwwwwwwBn...",
        "...nBBBBBBBBn...",
        "...nnnnnnnnnn...",
        "................",
        "................",
        "................",
        "................"],
    "user": [
        "................",
        "................",
        "................",
        "...kkkkkkkkkk...",
        "...kGGGGGGGGk...",
        "...kGGGGGGGGk...",
        "...kGGggggGGk...",
        "...kGGggggGGk...",
        "...kGGggggGGk...",
        "...kGGGGGGGGk...",
        "...kGGGGGGGGk...",
        "...kkkkkkkkkk...",
        "................",
        "................",
        "................",
        "................"],
    "comment": [
        "................",
        "................",
        "................",
        "....g..g........",
        "....g..g........",
        "..gggggggg......",
        "....g..g........",
        "..gggggggg......",
        "....g..g........",
        "....g..g........",
        "................",
        "................",
        "................",
        "................",
        "................",
        "................"],
    "disabled": [
        "................",
        "................",
        "................",
        "...ssssssssss...",
        "...sSSSSSSSSs...",
        "...sSsSSSSsSs...",
        "...sSSsSSsSSs...",
        "...sSSSssSSSs...",
        "...sSSSssSSSs...",
        "...sSSsSSsSSs...",
        "...sSsSSSSsSs...",
        "...ssssssssss...",
        "................",
        "................",
        "................",
        "................"],
}
ICONS.update({
    "open": [
        "................",
        "................",
        ".kkkk...........",
        "kYYYYk..........",
        "kYYYYkkkkkkk....",
        "kYYYYYYYYYYk....",
        "kYYkkkkkkkkkkk..",
        "kYkyyyyyyyyyyk..",
        "kYkyyyyyyyyyk...",
        "kkyyyyyyyyyyk...",
        "kkyyyyyyyyyk....",
        "kyyyyyyyyyyk....",
        "kkkkkkkkkkk.....",
        "................",
        "................",
        "................"],
    "save": [
        "................",
        ".kkkkkkkkkkkkk..",
        ".knnwwwwwwwwnk..",
        ".knnwwwwwwwwnk..",
        ".knnwwwwwwwwnk..",
        ".knnwwwwwwwwnk..",
        ".knnnnnnnnnnnk..",
        ".knnnnnnnnnnnk..",
        ".knnSSSSSSSnnk..",
        ".knnSSnnSSSnnk..",
        ".knnSSnnSSSnnk..",
        ".knnSSnnSSSnnk..",
        "..kkkkkkkkkkkk..",
        "................",
        "................",
        "................"],
    "cut": [
        "................",
        "...k.......k....",
        "...k.......k....",
        "....k.....k.....",
        "....k.....k.....",
        ".....k...k......",
        "......k.k.......",
        ".......k........",
        "......k.k.......",
        "...rrr...rrr....",
        "..r...r.r...r...",
        "..r...r.r...r...",
        "...rrr...rrr....",
        "................",
        "................",
        "................"],
    "copy": [
        "................",
        ".kkkkkkk........",
        ".kwwwwwk........",
        ".kwkkkwk........",
        ".kwwwwwkkkkkkk..",
        ".kwkkkwkwwwwwkk.",
        ".kwwwwwkwkkkwkwk",
        ".kwkkkwkwwwwwkkk",
        ".kkkkkkkwkkkkkwk",
        ".......kwwwwwwwk",
        ".......kwkkkkkwk",
        ".......kwwwwwwwk",
        ".......kkkkkkkkk",
        "................",
        "................",
        "................"],
    "paste": [
        "................",
        ".....kkkk.......",
        "..kkkYYYYkkk....",
        "..koookkooook...",
        "..koooooooook...",
        "..koookkkkkkkkk.",
        "..koookwwwwwwwk.",
        "..koookwkkkkkwk.",
        "..koookwwwwwwwk.",
        "..koookwkkkkkwk.",
        "..koookwwwwwwwk.",
        "..kkkkkwkkkkkwk.",
        ".......kkkkkkkk.",
        "................",
        "................",
        "................"],
    "help": [
        "................",
        ".....bbbbbb.....",
        "...bbBBBBBBbb...",
        "..bBBBwwwwBBBb..",
        "..bBBwwBBwwBBb..",
        ".bBBBBBBBwwBBBb.",
        ".bBBBBBBwwBBBBb.",
        ".bBBBBBwwBBBBBb.",
        ".bBBBBBwwBBBBBb.",
        "..bBBBBBBBBBBb..",
        "..bBBBBwwBBBBb..",
        "...bbBBwwBBbb...",
        ".....bbbbbb.....",
        "................",
        "................",
        "................"],
    "install": [
        "................",
        ".......gg.......",
        ".......gg.......",
        ".......gg.......",
        "....g..gg..g....",
        ".....g.gg.g.....",
        "......gggg......",
        ".......gg.......",
        "..kkkkkkkkkkkk..",
        "..kSSSSSSSSSSk..",
        "..kSSSSSSSgSSk..",
        "..kkkkkkkkkkkk..",
        "................",
        "................",
        "................",
        "................"],
    "blank": ["." * 1] * 16,
})
ICONS["down"] = list(reversed(ICONS["up"][:13])) + ICONS["up"][13:]


def make_icon(root, name):
    rows = ICONS[name]
    image = tk.PhotoImage(master=root, width=len(rows[0]), height=len(rows))
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            color = PALETTE.get(ch)
            if color:
                image.put(color, (x, y))
    return image


def make_icons(root):
    return {name: make_icon(root, name) for name in ICONS}
