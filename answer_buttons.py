# -*- coding: utf-8 -*-
#
# AJT Flexible Grading add-on for Anki 2.1
# Copyright (C) 2021  Ren Tatsumoto. <tatsu at autistici.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# Any modifications to this file must keep this entire header intact.
import json
import re
from typing import Callable

from anki.cards import Card
from anki.consts import *
from anki.hooks import wrap
from anki.lang import _
from aqt import gui_hooks
from aqt.reviewer import Reviewer

from .config import config
from .toolbar import LastEase

_ans_buttons_default = Reviewer._answerButtons


def add_vim_shortcuts(self: Reviewer, _old: Callable) -> list:
    # Credit: https://ankiweb.net/shared/info/1197299782
    class Shortcuts:
        _vim_shortcuts = [
            ("h", lambda: self._answerCard(BUTTON_ONE)),  # fail
            ("j", lambda: self._answerCard(BUTTON_TWO)),  # hard or good
            ("k", lambda: self._answerCard(self._defaultEase())),  # good
            ("l", lambda: self._answerCard(BUTTON_FOUR)),  # easy
            ("u", self.mw.onUndo),  # undo
            ("i", self.mw.onEditCurrent),  # edit
            (":", LastEase.open_last_card),  # last card
        ]
        _blocklist = ('1', '2', '3', '4',)
        _pass_fail_blocklist = ('j', 'l',)

        @classmethod
        def default(cls) -> list:
            return cls._vim_shortcuts + [(k, v) for k, v in _old(self) if k not in cls._blocklist]

        @classmethod
        def pass_fail(cls) -> list:
            return [(k, v) for k, v in cls.default() if k not in cls._pass_fail_blocklist]

    if config['pass_fail'] is True:
        # PassFail mode. Pressing 'Hard' and 'Easy' is not allowed.
        return Shortcuts.pass_fail()
    else:
        # Default shortcuts.
        return Shortcuts.default()


def answer_card(self: Reviewer, ease, _old: Callable):
    # Allows answering from the front side
    if config['flexible_grading'] is True and self.state == "question":
        self.state = "answer"

    # min() makes sure the original _answerCard() never skips
    _old(self, min(self.mw.col.sched.answerButtons(self.card), ease))


def only_pass_fail(buttons: tuple) -> tuple:
    edited_buttons = []
    for button in buttons:
        ease = button[0]
        label = button[1]
        if ease == BUTTON_ONE or ease == BUTTON_THREE:
            edited_buttons.append((ease, label))

    return tuple(edited_buttons)


def apply_label_colors(buttons: tuple) -> tuple:
    def color_label(ease, label):
        label = f"<font color=\"{config.get_color(ease)}\">{label}</font>"
        return ease, label

    edited_buttons = [color_label(*button) for button in buttons]
    return tuple(edited_buttons)


def filter_answer_buttons(buttons: tuple, _: Reviewer, __: Card) -> tuple:
    # Called by _answerButtonList, before _answerButtons gets called
    if config['pass_fail'] is True:
        buttons = only_pass_fail(buttons)

    if config['color_buttons'] is True:
        buttons = apply_label_colors(buttons)

    return buttons


def make_buttonless_ease_row(self: Reviewer) -> str:
    ease_row = []
    for ease, label in self._answerButtonList():
        attrs = f' style="color: {config.get_color(ease)};"' if config['color_buttons'] is True else ''
        ease_row.append(f'<div{attrs}>{self._buttonTime(ease)}</div>')
    return ''.join(ease_row)


def get_ease_row_css() -> str:
    return """
    <style>
    .ease_row {
        display: flex;
        justify-content: space-between;
        max-width: 400px;
        user-select: none;
    }
    .ease_row > div {
        padding-top: 1px;
    }
    </style>
    """


def wrap_buttonless_ease_row(html: str) -> str:
    return get_ease_row_css() + f'<div class="ease_row">{html}</div>'


def disable_buttons(html: str) -> str:
    return html.replace('<button', '<button disabled')


def make_backside_answer_buttons(self: Reviewer, _old: Callable) -> str:
    if config['remove_buttons'] is True:
        html = make_buttonless_ease_row(self)
        html = wrap_buttonless_ease_row(html)
    elif config['prevent_clicks'] is True:
        html: str = disable_buttons(_old(self))
    else:
        html: str = _old(self)

    return html


def make_show_ans_table_cell(self: Reviewer):
    stat_txt = make_stat_txt(self)
    show_answer_button = """<button title="%s" onclick='pycmd("ans");'>%s</button>""" % (
        _("Shortcut key: %s") % _("Space"),
        _("Show Answer"),
    )
    return f'<td align=center>{stat_txt}{show_answer_button}</td>'


def fix_spacer_padding(html: str) -> str:
    return '<style>.spacer{padding-top: 4px;}</style>' + html


def calc_middle_insert_pos(buttons_html_table: str) -> int:
    cell_positions = [m.start() for m in re.finditer('<td', buttons_html_table)]
    return cell_positions[:len(cell_positions) // 2 + 1][-1]


def make_flexible_front_row(self: Reviewer) -> str:
    ans_buttons = _ans_buttons_default(self)
    insert_pos = calc_middle_insert_pos(ans_buttons)
    html = ans_buttons[:insert_pos] + make_show_ans_table_cell(self) + ans_buttons[insert_pos:]
    if not self.mw.col.conf["estTimes"]:
        # If Prefs > Scheduling > Show next review time is False
        # Move answer buttons down a bit.
        html = fix_spacer_padding(html)
    return html


def get_stat_txt_style() -> str:
    padding_top = '5px' if config['remove_buttons'] is True else '4px'
    return f'padding: {padding_top} 5px 0px;'


def make_stat_txt(self: Reviewer) -> str:
    return f'<div style="{get_stat_txt_style()}">{self._remaining()}</div>'


def make_frontside_answer_buttons(self: Reviewer) -> None:
    html = None
    if config['remove_buttons'] is True:
        html = make_stat_txt(self)
    elif config['flexible_grading'] is True:
        html = make_flexible_front_row(self)
        if config['prevent_clicks'] is True:
            html = disable_buttons(html)
    if html is not None:
        self.bottom.web.eval("showAnswer(%s);" % json.dumps(html))
        self.bottom.web.adjustHeightToFit()


def main():
    # Add vim answer shortcuts
    Reviewer._shortcutKeys = wrap(Reviewer._shortcutKeys, add_vim_shortcuts, "around")

    # Activate Vim shortcuts on the front side, if enabled by the user.
    Reviewer._answerCard = wrap(Reviewer._answerCard, answer_card, "around")

    # (*) Create html layout for the answer buttons on the back side.
    # Buttons are either removed, disabled or left unchanged depending on config options.
    Reviewer._answerButtons = wrap(Reviewer._answerButtons, make_backside_answer_buttons, "around")

    # Wrap front side button(s).
    Reviewer._showAnswerButton = wrap(Reviewer._showAnswerButton, make_frontside_answer_buttons, "after")

    # Edit (ease, label) tuples which are used to create answer buttons.
    # If `color_buttons` is true, labels are colored.
    # If `pass_fail` is true, "Hard" and "Easy" buttons are removed.
    # This func gets called inside _answerButtonList, which itself gets called inside _answerButtons (*)
    gui_hooks.reviewer_will_init_answer_buttons.append(filter_answer_buttons)
