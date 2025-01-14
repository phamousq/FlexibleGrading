# Copyright: Ren Tatsumoto <tatsu at autistici.org>
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

from gettext import gettext as _

from aqt import mw
from aqt.qt import *
from aqt.utils import restoreGeom, saveGeom

from .ajt_common.widget_placement import place_widgets_in_grid
from .ajt_common.monospace_line_edit import MonoSpaceLineEdit
from .ajt_common.about_menu import menu_root_entry
from .ajt_common.consts import ADDON_SERIES
from .config import config, FlexibleGradingConfig
from .consts import *


def as_label(key: str) -> str:
    return key.replace('_', ' ').capitalize()


class ColorEdit(MonoSpaceLineEdit):
    font_size = 14
    min_height = 24

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        color_regex = QRegularExpression(r'^#?\w+$')
        color_validator = QRegularExpressionValidator(color_regex, self)
        self.setValidator(color_validator)
        self.setPlaceholderText("HTML color code")


class ColorEditPicker(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._edit = ColorEdit()
        self.setLayout(layout := QHBoxLayout())
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._edit)
        layout.addWidget(b := QPushButton(_("Pick")))
        b.setMinimumSize(32, 16)
        b.setBaseSize(32, 22)
        qconnect(b.clicked, self.choose_color)

    def choose_color(self):
        color = QColorDialog.getColor(initial=QColor.fromString(self._edit.text()))
        if color.isValid():
            self._edit.setText(color.name())

    def setText(self, text: str):
        return self._edit.setText(text)

    def text(self):
        return self._edit.text()


class SimpleKeyEdit(MonoSpaceLineEdit):
    font_size = 14
    min_height = 24

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        key_regex = QRegularExpression(r'^[-a-z0-9:;<>=?@~|`_/&!#$%^*(){}"+\]\[\\\']?$')
        key_validator = QRegularExpressionValidator(key_regex, self)
        self.setValidator(key_validator)
        self.setPlaceholderText("Key letter")
        self.setToolTip("If a key is taken by something else, it will refuse to work.\nLeave empty to disable.")


def make_color_line_edits() -> dict[str, ColorEditPicker]:
    d = {}
    for label in config.colors:
        d[label] = ColorEditPicker()
    return d


def make_answer_key_edits() -> dict[str, QLineEdit]:
    d = {}
    for label, button_key in config.buttons.items():
        d[label] = SimpleKeyEdit(button_key)
    return d


def make_toggleables() -> dict[str, QCheckBox]:
    """
    Automatically create QCheckBox instances for config keys with bool values.
    to avoid creating them by hand for each key.
    """
    d = {}
    for toggleable in config.bool_keys():
        if toggleable == 'color_buttons':
            continue
        d[toggleable] = QCheckBox(as_label(toggleable))
    return d


class SettingsMenuUI(QDialog):
    name = f"{ADDON_SERIES} {ADDON_NAME} Settings Dialog"
    _n_columns = 3

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowTitle(f'{ADDON_SERIES} {ADDON_NAME}')
        self.setMinimumSize(480, 512)
        self.colors = make_color_line_edits()
        self.answer_keys = make_answer_key_edits()
        self.toggleables = make_toggleables()
        self.color_buttons_gbox = QGroupBox("Color buttons")
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.restore_settings_button = self.button_box.addButton(
            _("Restore &Defaults"), QDialogButtonBox.ButtonRole.ResetRole
        )
        self.setLayout(self.setup_layout())
        self.add_tooltips()

    def setup_layout(self) -> QBoxLayout:
        layout = QVBoxLayout(self)
        layout.addLayout(self.make_settings_layout())
        layout.addWidget(self.button_box)
        return layout

    def make_settings_layout(self) -> QLayout:
        layout = QGridLayout()
        # row, col, row-span, col-span

        # Color buttons (pick colors)
        layout.addWidget(self.make_button_colors_group(), 0, 0, 1, 1)
        # Keys (assign letters)
        layout.addWidget(self.make_shortcuts_group(), 0, 1, 1, 1)
        # Buttons (remove, prevent clicks)
        layout.addWidget(self.make_buttons_group(), 1, 0, 1, 2)
        # Features (disable/enable pass-fail, flexible grading, etc.)
        layout.addWidget(self.make_features_group(), 2, 0, 1, 2)
        # Zoom behavior
        layout.addWidget(self.make_zoom_group(), 3, 0, 1, 2)
        return layout

    @staticmethod
    def make_colors_link():
        label = QLabel()
        label.setText(
            f'For the list of colors, see <a style="color: SteelBlue;" href="{HTML_COLORS_LINK}">w3schools.com</a>.'
        )
        label.setOpenExternalLinks(True)
        return label

    def make_button_colors_group(self) -> QGroupBox:
        gbox = self.color_buttons_gbox
        gbox.setCheckable(True)
        form = QFormLayout()
        for key, lineedit in self.colors.items():
            form.addRow(as_label(key), lineedit)
        form.addWidget(self.make_colors_link())
        gbox.setLayout(form)
        return gbox

    def make_shortcuts_group(self) -> QGroupBox:
        gbox = QGroupBox("Keys")
        gbox.setCheckable(False)
        form = QFormLayout()
        for key, key_edit in self.answer_keys.items():
            form.addRow(as_label(key), key_edit)
        gbox.setLayout(form)
        return gbox

    def make_buttons_group(self) -> QGroupBox:
        keys = (
            'remove_buttons',
            'prevent_clicks',
        )
        gbox = QGroupBox("Buttons")
        gbox.setCheckable(False)
        gbox.setLayout(place_widgets_in_grid(
            (self.toggleables[key] for key in keys),
            n_columns=self._n_columns,
        ))
        return gbox

    def make_features_group(self) -> QGroupBox:
        keys = (
            'pass_fail',
            'flexible_grading',
            'show_last_review',
            'hide_card_type',
            'press_good_key_to_flip_card',
        )
        gbox = QGroupBox("Features")
        gbox.setCheckable(False)
        gbox.setLayout(place_widgets_in_grid(
            (self.toggleables[key] for key in keys),
            n_columns=self._n_columns,
        ))
        return gbox

    def make_zoom_group(self) -> QGroupBox:
        keys = (
            'set_zoom_shortcuts',
            'remember_zoom_level',
            'tooltip_on_zoom_change',
        )
        gbox = QGroupBox("Zoom")
        gbox.setCheckable(False)
        gbox.setLayout(place_widgets_in_grid(
            (self.toggleables[key] for key in keys),
            n_columns=self._n_columns,
        ))
        return gbox

    def add_tooltips(self):
        self.toggleables['pass_fail'].setToolTip(
            '"Hard" and "Easy" buttons will be hidden.'
        )
        self.toggleables['flexible_grading'].setToolTip(
            "Grade cards from their front side\nwithout having to reveal the answer."
        )
        self.toggleables['remove_buttons'].setToolTip(
            "Remove answer buttons.\nOnly the corresponding intervals will be visible."
        )
        self.toggleables['prevent_clicks'].setToolTip(
            "Make answer buttons disabled.\n"
            "Disabled buttons are visible but unusable and un-clickable."
        )
        self.toggleables['show_last_review'].setToolTip(
            "Print the result of the last review on the toolbar."
        )
        self.toggleables['set_zoom_shortcuts'].setToolTip(
            "Change zoom value by pressing Ctrl+Plus and Ctrl+Minus."
        )
        self.toggleables['remember_zoom_level'].setToolTip(
            "Remember last zoom level and restore it on state change."
        )
        self.toggleables['tooltip_on_zoom_change'].setToolTip(
            "Show a tooltip when zoom level changes."
        )
        self.toggleables['hide_card_type'].setToolTip(
            "Turn off the indicator that tells you whether a card is new, review, or learn."
        )
        self.toggleables['press_good_key_to_flip_card'].setToolTip(
            "The \"good\" key (`k` by default) will be used\n"
            "to reveal the back side, similarly to the Space bar."
        )


class SettingsMenuDialog(SettingsMenuUI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connect_buttons()
        if mw.col.schedVer() < 2:
            self.layout().addWidget(QLabel(SCHED_NAG_MSG))
        self.restore_values(config)
        restoreGeom(self, self.name)

    def restore_values(self, cm: FlexibleGradingConfig):
        self.color_buttons_gbox.setChecked(cm['color_buttons'])
        for key, checkbox in self.toggleables.items():
            checkbox.setChecked(cm[key])
        for label, color_text in cm.colors.items():
            self.colors[label].setText(color_text)
        for label, key_letter in cm.buttons.items():
            self.answer_keys[label].setText(key_letter)

    def connect_buttons(self):
        qconnect(self.restore_settings_button.clicked, lambda: self.restore_values(FlexibleGradingConfig(default=True)))
        qconnect(self.button_box.accepted, self.accept)
        qconnect(self.button_box.rejected, self.reject)

    def accept(self) -> None:
        config['color_buttons'] = self.color_buttons_gbox.isChecked()
        for label, lineedit in self.colors.items():
            config.set_color(label, lineedit.text())
        for label, lineedit in self.answer_keys.items():
            config.set_key(label, lineedit.text())
        for key, checkbox in self.toggleables.items():
            config[key] = checkbox.isChecked()
        config.write_config()
        return super().accept()

    def done(self, *args, **kwargs) -> None:
        saveGeom(self, self.name)
        return super().done(*args, **kwargs)


def on_open_settings():
    if mw.state != "deckBrowser":
        mw.moveToState("deckBrowser")
    dialog = SettingsMenuDialog(mw)
    dialog.exec()


def setup_settings_action(parent: QWidget) -> QAction:
    action_settings = QAction(f"{ADDON_NAME} Options...", parent)
    qconnect(action_settings.triggered, on_open_settings)
    return action_settings


def main():
    root_menu = menu_root_entry()
    root_menu.addAction(setup_settings_action(root_menu))
