"""Native PyQt6 controller and widgets for Mini Task Manager."""

from __future__ import annotations

import time
from collections import OrderedDict
from datetime import datetime, timezone
from math import ceil
from pathlib import Path
from typing import Any

from PyQt6 import uic
from PyQt6.QtCore import (
    QEasingCurve,
    QEvent,
    QMimeData,
    QModelIndex,
    QObject,
    QPoint,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    QSequentialAnimationGroup,
    QTimer,
    Qt,
)
from PyQt6.QtGui import QColor, QDrag, QIcon, QPainter, QPainterPath, QPalette
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QColorDialog,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLayout,
    QLabel,
    QLineEdit,
    QListView,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyleOptionComboBox,
    QStyleOptionViewItem,
    QStylePainter,
    QStyledItemDelegate,
    QToolButton,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from models import (
    AVAILABLE_ICONS,
    DEFAULT_PRIORITY,
    PRIORITIES,
    CategoryRecord,
    TaskRecord,
    get_category,
    icon_label,
    normalize_completed_category_order,
    ordered_group_ids,
    reorder_pending_tasks_within_category_at_index,
    reorder_pending_tasks_within_category,
    reorder_records_by_id,
)
from icons import icon_size, material_icon, material_pixmap
from task_store import TaskStore


BASE_DIR = Path(__file__).resolve().parent
UI_FILE = BASE_DIR / "ui" / "main_window.ui"
APP_MIN_WIDTH = 1210
APP_MIN_HEIGHT = 600
ICON_PICKER_COLUMNS = 6
ICON_PICKER_ICON_SIZE = 24
ICON_PICKER_CELL_SIZE = 44
ICON_PICKER_SPACING = 4
ICON_PICKER_TOOLTIP_DELAY_MS = 500
PENDING_GROUP_RADIUS = 12
PENDING_GROUP_RIBBON_WIDTH = 6
CATEGORY_GRID_MIN_COLUMNS = 1
CATEGORY_GRID_MAX_COLUMNS = 3
CATEGORY_NAME_VISIBLE_CHARS = 10
CATEGORY_CHIP_WIDTH_REFERENCE_TEXT = f"{'n' * CATEGORY_NAME_VISIBLE_CHARS}..."
CATEGORY_CHIP_WIDTH_SCALE = 0.935
CATEGORY_CHIP_HORIZONTAL_MARGINS = 15
CATEGORY_CHIP_ITEM_SPACING = 4
CATEGORY_CHIP_DRAG_HANDLE_WIDTH = 14
CATEGORY_CHIP_ICON_WIDTH = 16
CATEGORY_CHIP_ACTION_WIDTH = 24
CATEGORY_CHIP_ACTION_ICON_SIZE = 14
CATEGORY_CHIP_ACTION_PRESSED_ICON_SIZE = 12
CATEGORY_EDITOR_WIDTH = 320
CATEGORY_EDITOR_COLOR_BUTTON_SIZE = 36
CATEGORY_EDITOR_ACTION_SIZE = 32
DRAG_KIND_CATEGORY = "category"
DRAG_KIND_TASK = "task"
DRAG_KIND_COMPLETED_CATEGORY = "completed-category"
DRAG_MIME_PREFIX = "application/x-mini-task-manager-"
TASK_DRAG_PLACEHOLDER_MIN_HEIGHT = 56


def truncated_category_name(name: str) -> str:
    if len(name) <= CATEGORY_NAME_VISIBLE_CHARS:
        return name
    return f"{name[:CATEGORY_NAME_VISIBLE_CHARS]}..."


def drag_mime_type(drag_kind: str) -> str:
    return f"{DRAG_MIME_PREFIX}{drag_kind}"


def encode_drag_payload(item_id: str, category_id: str = "") -> bytes:
    return f"{item_id}\n{category_id}".encode("utf-8")


def decode_drag_payload(mime_data: QMimeData, drag_kind: str) -> tuple[str, str] | None:
    mime_type = drag_mime_type(drag_kind)
    if not mime_data.hasFormat(mime_type):
        return None

    parts = bytes(mime_data.data(mime_type)).decode("utf-8").split("\n", 1)
    item_id = parts[0]
    category_id = parts[1] if len(parts) > 1 else ""
    if not item_id:
        return None
    return item_id, category_id


class PendingGroupFrame(QFrame):
    def __init__(self, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.color = safe_color(color)

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rounded_rect = QPainterPath()
        rounded_rect.addRoundedRect(QRectF(self.rect()), PENDING_GROUP_RADIUS, PENDING_GROUP_RADIUS)

        background = QColor(self.color)
        background.setAlphaF(0.07)
        painter.fillPath(rounded_rect, background)

        ribbon = QColor(self.color)
        ribbon.setAlphaF(0.38)
        painter.setClipPath(rounded_rect)
        painter.fillRect(QRectF(0, 0, PENDING_GROUP_RIBBON_WIDTH, self.height()), ribbon)
        painter.end()


class CategoryGridResizeFilter(QObject):
    def __init__(self, owner: Any) -> None:
        super().__init__(owner)
        self.owner = owner

    def eventFilter(self, watched: QObject | None, event: QEvent | None) -> bool:
        if event is not None and event.type() == QEvent.Type.Resize:
            QTimer.singleShot(0, self.owner.refresh_category_grid_columns)
        return super().eventFilter(watched, event)


class CategoryActionButton(QPushButton):
    def __init__(
        self,
        icon_name: str,
        icon_color: str,
        *,
        hover_icon_color: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("", parent)
        self.icon_name = icon_name
        self.icon_color = icon_color
        self.hover_icon_color = hover_icon_color or icon_color
        self._click_animation: QSequentialAnimationGroup | None = None

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setIcon(material_icon(self.icon_name, self.icon_color, CATEGORY_CHIP_ACTION_ICON_SIZE))
        self.setIconSize(icon_size(CATEGORY_CHIP_ACTION_ICON_SIZE))
        self.setFixedSize(CATEGORY_CHIP_ACTION_WIDTH, CATEGORY_CHIP_ACTION_WIDTH)
        self.pressed.connect(self.play_click_animation)

    def enterEvent(self, event: Any) -> None:
        self.setIcon(material_icon(self.icon_name, self.hover_icon_color, CATEGORY_CHIP_ACTION_ICON_SIZE))
        super().enterEvent(event)

    def leaveEvent(self, event: Any) -> None:
        self.setIcon(material_icon(self.icon_name, self.icon_color, CATEGORY_CHIP_ACTION_ICON_SIZE))
        super().leaveEvent(event)

    def play_click_animation(self) -> None:
        if self._click_animation is not None:
            self._click_animation.stop()

        normal_size = icon_size(CATEGORY_CHIP_ACTION_ICON_SIZE)
        pressed_size = icon_size(CATEGORY_CHIP_ACTION_PRESSED_ICON_SIZE)
        self.setIconSize(normal_size)

        animation = QSequentialAnimationGroup(self)
        shrink = QPropertyAnimation(self, b"iconSize", animation)
        shrink.setDuration(45)
        shrink.setStartValue(normal_size)
        shrink.setEndValue(pressed_size)
        shrink.setEasingCurve(QEasingCurve.Type.OutCubic)

        expand = QPropertyAnimation(self, b"iconSize", animation)
        expand.setDuration(85)
        expand.setStartValue(pressed_size)
        expand.setEndValue(normal_size)
        expand.setEasingCurve(QEasingCurve.Type.OutBack)

        animation.addAnimation(shrink)
        animation.addAnimation(expand)
        animation.finished.connect(lambda: setattr(self, "_click_animation", None))
        self._click_animation = animation
        animation.start()


class DragHandle(QLabel):
    def __init__(
        self,
        owner: Any,
        drag_kind: str,
        item_id: str,
        category_id: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("::", parent)
        self.owner = owner
        self.drag_kind = drag_kind
        self.item_id = item_id
        self.category_id = category_id
        self.drag_start_position = QPoint()

        self.setObjectName("dragHandle")
        self.setToolTip("Arrastrar para reordenar")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setFixedWidth(CATEGORY_CHIP_DRAG_HANDLE_WIDTH)

    def mousePressEvent(self, event: Any) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = event.position().toPoint() if hasattr(event, "position") else event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: Any) -> None:
        if not event.buttons() & Qt.MouseButton.LeftButton:
            return

        position = event.position().toPoint() if hasattr(event, "position") else event.pos()
        if (position - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
            return

        owner = self.owner
        drag = QDrag(owner)
        mime_data = QMimeData()
        mime_data.setData(drag_mime_type(self.drag_kind), encode_drag_payload(self.item_id, self.category_id))
        drag.setMimeData(mime_data)
        source_card = self._source_drop_frame()
        if source_card is not None:
            pixmap = source_card.grab()
            drag.setPixmap(pixmap)
            drag.setHotSpot(source_card.mapFromGlobal(self.mapToGlobal(position)))

        if self.drag_kind == DRAG_KIND_TASK:
            owner.begin_task_drag(self.item_id, self.category_id, source_card)
        try:
            drag.exec(Qt.DropAction.MoveAction)
        finally:
            if self.drag_kind == DRAG_KIND_TASK:
                owner.end_task_drag()

    def _source_drop_frame(self) -> QFrame | None:
        widget = self.parentWidget()
        while widget is not None:
            if isinstance(widget, ReorderDropFrame):
                return widget
            widget = widget.parentWidget()
        return None


class ReorderDropFrame(QFrame):
    def __init__(
        self,
        owner: Any,
        drag_kind: str,
        target_id: str,
        target_category_id: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.owner = owner
        self.drag_kind = drag_kind
        self.target_id = target_id
        self.target_category_id = target_category_id
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: Any) -> None:
        if self._can_accept(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: Any) -> None:
        if self.drag_kind == DRAG_KIND_TASK and self._preview_task_drop(event):
            event.acceptProposedAction()
        elif self._can_accept(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: Any) -> None:
        payload = decode_drag_payload(event.mimeData(), self.drag_kind)
        if payload is None:
            event.ignore()
            return

        moved_id, moved_category_id = payload
        if self.drag_kind == DRAG_KIND_TASK:
            did_move = self.owner.handle_task_reorder_drop(
                moved_id,
                moved_category_id,
                self.target_id,
                self.target_category_id,
                self._drop_after(event),
            )
        else:
            did_move = self.owner.handle_reorder_drop(
                self.drag_kind,
                moved_id,
                moved_category_id,
                self.target_id,
                self.target_category_id,
            )
        if did_move:
            event.acceptProposedAction()
        else:
            event.ignore()

    def _can_accept(self, event: Any) -> bool:
        payload = decode_drag_payload(event.mimeData(), self.drag_kind)
        if payload is None:
            return False
        moved_id, moved_category_id = payload
        return self.owner.can_drop_reorder(
            self.drag_kind,
            moved_id,
            moved_category_id,
            self.target_id,
            self.target_category_id,
        )

    def _preview_task_drop(self, event: Any) -> bool:
        payload = decode_drag_payload(event.mimeData(), DRAG_KIND_TASK)
        if payload is None:
            return False
        moved_id, moved_category_id = payload
        return self.owner.preview_task_reorder(
            moved_id,
            moved_category_id,
            self.target_id,
            self.target_category_id,
            self._drop_after(event),
        )

    def _drop_after(self, event: Any) -> bool:
        position = event.position().toPoint() if hasattr(event, "position") else event.pos()
        return position.y() >= self.height() / 2


class TaskDragPlaceholder(QFrame):
    def __init__(self, owner: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.owner = owner
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: Any) -> None:
        if self._can_accept(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: Any) -> None:
        if self._can_accept(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: Any) -> None:
        payload = decode_drag_payload(event.mimeData(), DRAG_KIND_TASK)
        if payload is None:
            event.ignore()
            return

        moved_id, moved_category_id = payload
        if self.owner.handle_task_reorder_preview_drop(moved_id, moved_category_id):
            event.acceptProposedAction()
        else:
            event.ignore()

    def _can_accept(self, event: Any) -> bool:
        payload = decode_drag_payload(event.mimeData(), DRAG_KIND_TASK)
        if payload is None:
            return False
        moved_id, moved_category_id = payload
        return self.owner.can_drop_task_reorder_preview(moved_id, moved_category_id)


class CenteredComboPaintFilter(QObject):
    def __init__(self, combo: QWidget, *, center_on_button: bool = False) -> None:
        super().__init__(combo)
        self.combo = combo
        self.center_on_button = center_on_button

    def eventFilter(self, watched: QObject | None, event: QEvent | None) -> bool:
        if watched is self.combo and event is not None and event.type() == QEvent.Type.Paint:
            self._paint_combo()
            return True
        return super().eventFilter(watched, event)

    def _paint_combo(self) -> None:
        option = QStyleOptionComboBox()
        self.combo.initStyleOption(option)
        painter = QStylePainter(self.combo)
        frame_option = QStyleOptionComboBox(option)
        frame_option.currentText = ""
        frame_option.currentIcon = QIcon()
        painter.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, frame_option)
        self._draw_centered_label(option, painter)

    def _draw_centered_label(
        self,
        option: QStyleOptionComboBox,
        painter: Any,
    ) -> None:
        edit_rect = self.combo.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox,
            option,
            QStyle.SubControl.SC_ComboBoxEditField,
            self.combo,
        )
        text = option.currentText
        icon = option.currentIcon
        icon_size_value = min(option.iconSize.width(), option.iconSize.height(), ICON_PICKER_ICON_SIZE)
        icon_width = icon_size_value if not icon.isNull() else 0
        spacing = 6 if icon_width and text else 0
        text_width = option.fontMetrics.horizontalAdvance(text) if text else 0
        content_rect = self.combo.rect() if self.center_on_button else edit_rect
        content_width = icon_width + spacing + text_width
        start_x = content_rect.x() + max(0, (content_rect.width() - content_width) // 2)
        text_start_x = start_x + icon_width + spacing

        if icon_width:
            icon_rect = QRect(
                start_x,
                content_rect.y() + (content_rect.height() - icon_width) // 2,
                icon_width,
                icon_width,
            )
            icon.paint(painter, icon_rect, Qt.AlignmentFlag.AlignCenter)

        if text:
            painter.save()
            color_group = (
                QPalette.ColorGroup.Active
                if option.state & QStyle.StateFlag.State_Enabled
                else QPalette.ColorGroup.Disabled
            )
            painter.setPen(option.palette.color(color_group, QPalette.ColorRole.Text))
            painter.drawText(
                QRect(text_start_x, content_rect.y(), text_width, content_rect.height()),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                text,
            )
            painter.restore()


class IconGridDelegate(QStyledItemDelegate):
    def paint(self, painter: Any, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        icon_option = QStyleOptionViewItem(option)
        self.initStyleOption(icon_option, index)
        icon_option.text = ""
        icon_option.decorationAlignment = Qt.AlignmentFlag.AlignCenter
        icon_option.decorationSize = icon_size(ICON_PICKER_ICON_SIZE)
        icon_option.displayAlignment = Qt.AlignmentFlag.AlignCenter
        icon_option.features &= ~QStyleOptionViewItem.ViewItemFeature.HasDisplay

        style = icon_option.widget.style() if icon_option.widget else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, icon_option, painter, icon_option.widget)

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        return QSize(ICON_PICKER_CELL_SIZE, ICON_PICKER_CELL_SIZE)


class IconGridPopupFilter(QObject):
    def __init__(self, view: QListView, view_size: QSize, delay_ms: int) -> None:
        super().__init__(view)
        self.view = view
        self.view_size = QSize(view_size)
        self.popup_size = QSize(view_size.width() + 2, view_size.height() + 2)
        self.viewport = view.viewport()
        self.hovered_index = QModelIndex()
        self.hover_pos = QPoint()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(delay_ms)
        self.timer.timeout.connect(self._show_tooltip)

    def eventFilter(self, watched: QObject | None, event: QEvent | None) -> bool:
        if watched is self.view and event is not None:
            if event.type() == QEvent.Type.Show:
                QTimer.singleShot(0, self._resize_popup)
            elif event.type() == QEvent.Type.Hide:
                self.cancel()
        elif watched is self.viewport and event is not None:
            try:
                event_type = event.type()
                if event_type == QEvent.Type.MouseMove:
                    position = event.position().toPoint() if hasattr(event, "position") else event.pos()
                    self._set_hovered_index(self.view.indexAt(position), position)
                elif event_type in {
                    QEvent.Type.Leave,
                    QEvent.Type.MouseButtonPress,
                    QEvent.Type.Wheel,
                    QEvent.Type.Hide,
                }:
                    self.cancel()
            except RuntimeError:
                self.timer.stop()

        return super().eventFilter(watched, event)

    def _resize_popup(self) -> None:
        try:
            popup = self.view.window()
            popup.setMinimumSize(self.popup_size)
            popup.setMaximumSize(self.popup_size)
            popup.resize(self.popup_size)
            self.view.setGeometry(1, 1, self.view_size.width(), self.view_size.height())
        except RuntimeError:
            self.timer.stop()

    def cancel(self) -> None:
        self.timer.stop()
        self.hovered_index = QModelIndex()
        QToolTip.hideText()

    def _set_hovered_index(self, index: QModelIndex, position: QPoint) -> None:
        self.hover_pos = QPoint(position)
        if index == self.hovered_index:
            return

        QToolTip.hideText()
        self.hovered_index = QModelIndex(index)
        if self.hovered_index.isValid():
            self.timer.start()
        else:
            self.timer.stop()

    def _show_tooltip(self) -> None:
        try:
            if not self.hovered_index.isValid() or not self.view.isVisible():
                return

            if self.view.indexAt(self.hover_pos) != self.hovered_index:
                return

            text = self.hovered_index.data(Qt.ItemDataRole.AccessibleTextRole)
            if text:
                QToolTip.showText(self.viewport.mapToGlobal(self.hover_pos), str(text), self.viewport)
        except RuntimeError:
            self.timer.stop()


class MainWindow(QMainWindow):
    def __init__(self, data_file: Path | str) -> None:
        super().__init__()
        uic.loadUi(UI_FILE, self)

        self.store = TaskStore(data_file)
        data = self.store.load()
        self.tasks: list[TaskRecord] = data["tasks"]
        self.categories: list[CategoryRecord] = data["categories"]
        self.completed_category_order = data["completedCategoryOrder"]

        self.collapsed_categories: set[str] = set()
        self.collapsed_completed_categories: set[str] = set()
        self.current_stat_filter = "hoy"
        self.selected_category_color = "#68abff"
        self.category_grid_columns = 0
        self.category_list_width = 0
        self.active_category_editor_id: str | None = None
        self.active_category_editor_draft: dict[str, str] | None = None
        self.dragging_task_id: str | None = None
        self.dragging_task_category_id: str | None = None
        self.task_drag_preview_category_id: str | None = None
        self.task_drag_preview_index: int | None = None
        self.task_drag_placeholder_height = TASK_DRAG_PLACEHOLDER_MIN_HEIGHT
        self.task_drag_source_card: QWidget | None = None
        self.task_drag_placeholder: QFrame | None = None

        self._configure_ui()
        self.refresh_all()

    def _configure_ui(self) -> None:
        self.setWindowTitle("Mini Task Manager")
        self.resize(1280, 800)
        self.setMinimumSize(APP_MIN_WIDTH, APP_MIN_HEIGHT)
        self.setStyleSheet(APP_STYLES)

        self.dashboardLayout.setStretch(0, 3)
        self.dashboardLayout.setStretch(1, 5)
        self.dashboardLayout.setStretch(2, 4)

        self.categories_grid = QGridLayout(self.categoriesListWidget)
        self.categories_grid.setContentsMargins(0, 0, 0, 0)
        self.categories_grid.setHorizontalSpacing(4)
        self.categories_grid.setVerticalSpacing(8)
        self._category_grid_resize_filter = CategoryGridResizeFilter(self)
        self.categoriesListWidget.installEventFilter(self._category_grid_resize_filter)

        self._configure_icon_combo(self.categoryIconCombo)
        self._configure_task_combos()
        self._fill_icon_combo(self.categoryIconCombo)
        self._fill_priority_combo()
        self._set_category_color(self.selected_category_color)

        self.categoryColorButton.clicked.connect(self.pick_category_color)
        self.addCategoryButton.clicked.connect(self.add_category)
        self.categoryNameEdit.returnPressed.connect(self.add_category)
        self.addTaskButton.clicked.connect(self.add_task)
        self.taskTitleEdit.returnPressed.connect(self.add_task)

        self.filterTodayButton.clicked.connect(lambda: self.set_stat_filter("hoy"))
        self.filterWeekButton.clicked.connect(lambda: self.set_stat_filter("semana"))
        self.filterMonthButton.clicked.connect(lambda: self.set_stat_filter("mes"))
        self._update_filter_buttons()

    def _configure_icon_combo(self, combo: QComboBox) -> None:
        view = QListView(combo)
        rows = (len(AVAILABLE_ICONS) + ICON_PICKER_COLUMNS - 1) // ICON_PICKER_COLUMNS
        popup_width = ICON_PICKER_COLUMNS * (ICON_PICKER_CELL_SIZE + ICON_PICKER_SPACING) + ICON_PICKER_SPACING
        popup_height = rows * (ICON_PICKER_CELL_SIZE + ICON_PICKER_SPACING) + ICON_PICKER_SPACING

        view.setObjectName("categoryIconGridPopup")
        view.setViewMode(QListView.ViewMode.IconMode)
        view.setFlow(QListView.Flow.LeftToRight)
        view.setWrapping(True)
        view.setResizeMode(QListView.ResizeMode.Adjust)
        view.setMovement(QListView.Movement.Static)
        view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        view.setUniformItemSizes(True)
        view.setSpacing(ICON_PICKER_SPACING)
        view_size = QSize(popup_width, popup_height)
        view.setGridSize(QSize(ICON_PICKER_CELL_SIZE, ICON_PICKER_CELL_SIZE))
        view.setIconSize(icon_size(ICON_PICKER_ICON_SIZE))
        view.setFixedSize(view_size)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        view.setMouseTracking(True)
        view.viewport().setMouseTracking(True)

        icon_grid_delegate = IconGridDelegate(view)
        view.setItemDelegate(icon_grid_delegate)
        combo.setView(view)
        centered_icon_combo_paint_filter = CenteredComboPaintFilter(combo)
        combo.installEventFilter(centered_icon_combo_paint_filter)
        combo.setIconSize(icon_size(ICON_PICKER_ICON_SIZE))
        combo.setMaxVisibleItems(rows)
        combo.setFixedSize(112, 42)
        icon_popup_filter = IconGridPopupFilter(view, view_size, ICON_PICKER_TOOLTIP_DELAY_MS)
        view.installEventFilter(icon_popup_filter)
        view.viewport().installEventFilter(icon_popup_filter)

        combo._icon_grid_delegate = icon_grid_delegate
        combo._centered_icon_combo_paint_filter = centered_icon_combo_paint_filter
        combo._icon_popup_filter = icon_popup_filter

    def _configure_task_combos(self) -> None:
        self._centered_task_category_combo_paint_filter = CenteredComboPaintFilter(
            self.taskCategoryCombo,
            center_on_button=True,
        )
        self.taskCategoryCombo.installEventFilter(self._centered_task_category_combo_paint_filter)

        self._centered_task_priority_combo_paint_filter = CenteredComboPaintFilter(
            self.taskPriorityCombo,
            center_on_button=True,
        )
        self.taskPriorityCombo.installEventFilter(self._centered_task_priority_combo_paint_filter)

    def _fill_icon_combo(self, combo: QComboBox) -> None:
        combo.clear()
        combo.setIconSize(icon_size(ICON_PICKER_ICON_SIZE))
        for icon_name in AVAILABLE_ICONS:
            combo.addItem(
                material_icon(icon_name, "#4e453c", ICON_PICKER_ICON_SIZE),
                icon_label(icon_name),
                icon_name,
            )
            index = combo.count() - 1
            combo.setItemData(index, icon_label(icon_name), Qt.ItemDataRole.AccessibleTextRole)

    def _fill_priority_combo(self) -> None:
        self.taskPriorityCombo.clear()
        self.taskPriorityCombo.setIconSize(icon_size(16))
        for priority in PRIORITIES:
            self.taskPriorityCombo.addItem(material_icon("flag", priority_color(priority), 16), priority, priority)
        self.taskPriorityCombo.setCurrentText(DEFAULT_PRIORITY)

    def refresh_all(self) -> None:
        self.render_categories()
        self.update_category_select()
        self.render_tasks()
        self.render_stats()

    def render_categories(self) -> None:
        clear_layout(self.categories_grid)
        columns = self._category_grid_columns()
        self.category_grid_columns = columns
        self.category_list_width = self.categoriesListWidget.width()

        if not self.categories:
            self.active_category_editor_id = None
            self.active_category_editor_draft = None
            empty = QLabel("No hay categorías todavía.")
            empty.setObjectName("emptyStateLabel")
            empty.setWordWrap(True)
            self.categories_grid.addWidget(empty, 0, 0, 1, columns)
            return

        if self.active_category_editor_id and not any(
            category.get("id") == self.active_category_editor_id for category in self.categories
        ):
            self.active_category_editor_id = None
            self.active_category_editor_draft = None

        chip_width = self._category_chip_width()
        grid_row = 0
        for row_start in range(0, len(self.categories), columns):
            row_categories = self.categories[row_start : row_start + columns]
            active_category: CategoryRecord | None = None
            active_column = 0

            for column, category in enumerate(row_categories):
                category_id = str(category.get("id", ""))
                chip = self._category_chip(category, chip_width)
                self.categories_grid.addWidget(chip, grid_row, column, Qt.AlignmentFlag.AlignCenter)
                if category_id == self.active_category_editor_id:
                    active_category = category
                    active_column = column

            grid_row += 1
            if active_category is not None:
                self.categories_grid.addWidget(
                    self._category_editor_row(active_category, active_column, columns),
                    grid_row,
                    0,
                    1,
                    columns,
                )
                grid_row += 1

    def _category_chip(self, category: CategoryRecord, chip_width: int) -> QFrame:
        category_id = str(category.get("id", ""))
        chip = ReorderDropFrame(self, DRAG_KIND_CATEGORY, category_id)
        chip.setObjectName("categoryChip")
        chip.setFixedWidth(chip_width)
        chip.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        name = str(category.get("name", ""))
        chip.setToolTip(name)
        color = safe_color(category.get("color"))
        text_color = readable_color(color)
        chip.setStyleSheet(
            f"""
            QFrame#categoryChip {{
                background-color: {qss_rgba(color, 0.15)};
                border: 1px solid {qss_rgba(color, 0.28)};
                border-radius: 14px;
            }}
            QLabel {{
                color: {text_color};
                font-size: 12px;
                font-weight: 700;
            }}
            QPushButton {{
                color: {text_color};
                background: transparent;
                border: none;
                border-radius: 6px;
                font-weight: 700;
                padding: 0;
            }}
            QPushButton#editCategoryButton:hover,
            QPushButton#deleteCategoryButton:hover {{
                background-color: {qss_rgba(text_color, 0.13)};
            }}
            QPushButton#editCategoryButton:pressed,
            QPushButton#deleteCategoryButton:pressed {{
                background-color: {qss_rgba(text_color, 0.22)};
            }}
            """
        )

        row = QHBoxLayout(chip)
        row.setContentsMargins(8, 5, 7, 5)
        row.setSpacing(CATEGORY_CHIP_ITEM_SPACING)

        icon = QLabel()
        icon.setPixmap(material_pixmap(str(category.get("icon", "label")), text_color, 14))
        icon.setFixedSize(CATEGORY_CHIP_ICON_WIDTH, CATEGORY_CHIP_ICON_WIDTH)
        label = QLabel(truncated_category_name(name))
        label.setToolTip(name)
        label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

        edit_button = CategoryActionButton("edit_document", text_color)
        edit_button.setObjectName("editCategoryButton")
        edit_button.setToolTip("Editar categoría")
        edit_button.clicked.connect(
            lambda checked=False, category_id=str(category.get("id", "")): self.toggle_category_editor(category_id)
        )

        delete_button = CategoryActionButton("close", text_color)
        delete_button.setObjectName("deleteCategoryButton")
        delete_button.setToolTip("Eliminar categoría")
        delete_button.clicked.connect(
            lambda checked=False, category_id=str(category.get("id", "")): self.delete_category(category_id)
        )

        row.addWidget(DragHandle(self, DRAG_KIND_CATEGORY, category_id))
        row.addWidget(icon)
        row.addWidget(label)
        row.addStretch(1)
        row.addWidget(edit_button)
        row.addWidget(delete_button)
        return chip

    def _category_editor_row(self, category: CategoryRecord, active_column: int, columns: int) -> QWidget:
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        spacing = max(0, self.categories_grid.horizontalSpacing())
        available_width = max(1, self.categoriesListWidget.width())
        editor_width = min(CATEGORY_EDITOR_WIDTH, available_width)
        cell_width = (available_width - (spacing * max(0, columns - 1))) / max(1, columns)
        editor_left = round((active_column * (cell_width + spacing)) + (cell_width / 2) - (editor_width / 2))
        editor_left = max(0, min(editor_left, max(0, available_width - editor_width)))

        layout.setContentsMargins(editor_left, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._category_editor(category, editor_width))
        layout.addStretch(1)
        return wrapper

    def _category_editor(self, category: CategoryRecord, editor_width: int) -> QFrame:
        category_id = str(category.get("id", ""))
        draft = self.active_category_editor_draft or self._category_editor_draft(category)
        color_state = {"value": safe_color(draft.get("color"))}

        editor = QFrame()
        editor.setObjectName("categoryEditor")
        editor.setFixedWidth(editor_width)
        editor.setStyleSheet(
            f"""
            QFrame#categoryEditor {{
                background-color: #fbf9f5;
                border: 1px solid {qss_rgba(color_state["value"], 0.32)};
                border-radius: 10px;
            }}
            QLineEdit#categoryEditorNameEdit {{
                background-color: #e4e2de;
                border: none;
                border-radius: 8px;
                padding: 7px 10px;
                font-size: 13px;
            }}
            QLineEdit#categoryEditorNameEdit[invalid="true"] {{
                border: 1px solid #ba1a1a;
                padding: 6px 9px;
            }}
            QPushButton#categoryEditorColorButton {{
                border: 3px solid #ffffff;
                border-radius: 18px;
                padding: 0;
            }}
            QPushButton#categoryEditorColorButton:hover {{
                border-color: #d1c4b8;
            }}
            QPushButton#categoryEditorSaveButton,
            QPushButton#categoryEditorCancelButton {{
                background-color: #e4e2de;
                border: none;
                border-radius: 8px;
                padding: 0;
            }}
            QPushButton#categoryEditorSaveButton:hover,
            QPushButton#categoryEditorCancelButton:hover {{
                background-color: #d8d4ce;
            }}
            """
        )
        layout = QVBoxLayout(editor)
        layout.setContentsMargins(10, 9, 10, 9)
        layout.setSpacing(7)

        name_edit = QLineEdit(draft.get("name", ""))
        name_edit.setObjectName("categoryEditorNameEdit")
        name_edit.setPlaceholderText("Nombre")
        name_edit.setProperty("invalid", False)

        controls_row = QWidget()
        controls_layout = QHBoxLayout(controls_row)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(7)

        color_button = QPushButton("")
        color_button.setObjectName("categoryEditorColorButton")
        color_button.setToolTip("Elegir color")
        color_button.setFixedSize(CATEGORY_EDITOR_COLOR_BUTTON_SIZE, CATEGORY_EDITOR_COLOR_BUTTON_SIZE)
        self._set_editor_color_button(color_button, color_state["value"])

        icon_combo = QComboBox()
        icon_combo.setObjectName("categoryIconCombo")
        self._configure_icon_combo(icon_combo)
        self._fill_icon_combo(icon_combo)
        icon_index = icon_combo.findData(draft.get("icon") or "label")
        icon_combo.setCurrentIndex(max(0, icon_index))

        save_button = QPushButton("")
        save_button.setObjectName("categoryEditorSaveButton")
        save_button.setIcon(material_icon("check", "#4e453c", 16))
        save_button.setIconSize(icon_size(16))
        save_button.setToolTip("Guardar cambios")
        save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        save_button.setFixedSize(CATEGORY_EDITOR_ACTION_SIZE, CATEGORY_EDITOR_ACTION_SIZE)

        cancel_button = QPushButton("")
        cancel_button.setObjectName("categoryEditorCancelButton")
        cancel_button.setIcon(material_icon("close", "#4e453c", 16))
        cancel_button.setIconSize(icon_size(16))
        cancel_button.setToolTip("Cancelar")
        cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_button.setFixedSize(CATEGORY_EDITOR_ACTION_SIZE, CATEGORY_EDITOR_ACTION_SIZE)

        def pick_editor_color() -> None:
            color = QColorDialog.getColor(QColor(color_state["value"]), self, "Elegir color")
            if color.isValid():
                color_state["value"] = safe_color(color.name())
                self._update_category_editor_draft("color", color_state["value"])
                self._set_editor_color_button(color_button, color_state["value"])

        def save_editor() -> None:
            name = name_edit.text().strip()
            if not name:
                self._set_line_edit_invalid(name_edit, True)
                name_edit.setFocus()
                return
            self.save_category_editor(category_id, name, color_state["value"], icon_combo.currentData() or "label")

        def update_name_draft(text: str) -> None:
            self._update_category_editor_draft("name", text)
            if text.strip():
                self._set_line_edit_invalid(name_edit, False)

        color_button.clicked.connect(pick_editor_color)
        name_edit.textChanged.connect(update_name_draft)
        icon_combo.currentIndexChanged.connect(
            lambda index: self._update_category_editor_draft("icon", icon_combo.itemData(index) or "label")
        )
        name_edit.returnPressed.connect(save_editor)
        save_button.clicked.connect(save_editor)
        cancel_button.clicked.connect(self.close_category_editor)

        controls_layout.addWidget(color_button)
        controls_layout.addWidget(icon_combo)
        controls_layout.addStretch(1)
        controls_layout.addWidget(save_button)
        controls_layout.addWidget(cancel_button)
        layout.addWidget(name_edit)
        layout.addWidget(controls_row)
        QTimer.singleShot(0, name_edit.setFocus)
        return editor

    def _set_editor_color_button(self, button: QPushButton, color: str) -> None:
        button.setStyleSheet(
            f"""
            QPushButton#categoryEditorColorButton {{
                background-color: {safe_color(color)};
                border: 3px solid #ffffff;
                border-radius: 18px;
                padding: 0;
            }}
            QPushButton#categoryEditorColorButton:hover {{
                border-color: #d1c4b8;
            }}
            """
        )

    def _set_line_edit_invalid(self, line_edit: QLineEdit, invalid: bool) -> None:
        line_edit.setProperty("invalid", invalid)
        line_edit.style().unpolish(line_edit)
        line_edit.style().polish(line_edit)

    def toggle_category_editor(self, category_id: str) -> None:
        if self.active_category_editor_id == category_id:
            self.active_category_editor_id = None
            self.active_category_editor_draft = None
        else:
            category = get_category(self.categories, category_id)
            self.active_category_editor_id = category_id
            self.active_category_editor_draft = self._category_editor_draft(category)
        self.render_categories()

    def close_category_editor(self) -> None:
        self.active_category_editor_id = None
        self.active_category_editor_draft = None
        self.render_categories()

    def save_category_editor(self, category_id: str, name: str, color: str, icon_name: str) -> None:
        for category in self.categories:
            if category.get("id") == category_id:
                category["name"] = name
                category["color"] = safe_color(color)
                category["icon"] = icon_name if icon_name in AVAILABLE_ICONS else "label"
                break
        else:
            self.active_category_editor_id = None
            self.active_category_editor_draft = None
            self.render_categories()
            return

        self.active_category_editor_id = None
        self.active_category_editor_draft = None
        self.render_categories()
        self.update_category_select()
        self.render_tasks()
        self.render_stats()
        self._save()

    def _category_editor_draft(self, category: CategoryRecord) -> dict[str, str]:
        return {
            "name": str(category.get("name", "")),
            "color": safe_color(category.get("color")),
            "icon": str(category.get("icon") or "label"),
        }

    def _update_category_editor_draft(self, key: str, value: str) -> None:
        if self.active_category_editor_draft is not None:
            self.active_category_editor_draft[key] = value

    def _category_chip_width(self) -> int:
        label_probe = QLabel()
        label_probe.setStyleSheet("font-size: 12px; font-weight: 700;")
        label_probe.ensurePolished()
        reference_label_width = label_probe.fontMetrics().horizontalAdvance(CATEGORY_CHIP_WIDTH_REFERENCE_TEXT)
        base_width = (
            CATEGORY_CHIP_HORIZONTAL_MARGINS
            + CATEGORY_CHIP_DRAG_HANDLE_WIDTH
            + CATEGORY_CHIP_ICON_WIDTH
            + reference_label_width
            + (CATEGORY_CHIP_ACTION_WIDTH * 2)
            + (CATEGORY_CHIP_ITEM_SPACING * 5)
        )
        return ceil(base_width * CATEGORY_CHIP_WIDTH_SCALE)

    def _category_grid_columns(self) -> int:
        available_width = self.categoriesListWidget.width()
        chip_width = self._category_chip_width()
        spacing = max(0, self.categories_grid.horizontalSpacing())
        columns = CATEGORY_GRID_MIN_COLUMNS

        for candidate in range(CATEGORY_GRID_MIN_COLUMNS + 1, CATEGORY_GRID_MAX_COLUMNS + 1):
            required_width = (chip_width * candidate) + (spacing * (candidate - 1))
            if available_width >= required_width:
                columns = candidate

        return columns

    def refresh_category_grid_columns(self) -> None:
        columns = self._category_grid_columns()
        width = self.categoriesListWidget.width()
        if columns != self.category_grid_columns or (
            self.active_category_editor_id and width != self.category_list_width
        ):
            self.render_categories()

    def update_category_select(self) -> None:
        current_value = self.taskCategoryCombo.currentData()
        self.taskCategoryCombo.clear()
        self.taskCategoryCombo.setIconSize(icon_size(16))
        self.taskCategoryCombo.addItem("Categoría", None)

        for category in self.categories:
            color = readable_color(safe_color(category.get("color")))
            self.taskCategoryCombo.addItem(
                material_icon(str(category.get("icon", "label")), color, 16),
                str(category.get("name", "")),
                category.get("id"),
            )

        if current_value and any(category.get("id") == current_value for category in self.categories):
            self.taskCategoryCombo.setCurrentIndex(self.taskCategoryCombo.findData(current_value))
        else:
            self.taskCategoryCombo.setCurrentIndex(0)

    def render_tasks(self) -> None:
        clear_layout(self.taskGroupsLayout)
        pending_tasks = [task for task in self.tasks if not task.get("completed")]

        if not pending_tasks:
            self.taskGroupsLayout.addWidget(
                self._empty_card("No hay tareas pendientes. Tómate un descanso.", icon_name="done_all")
            )
            self.taskGroupsLayout.addStretch(1)
            return

        grouped_tasks = grouped_by_category(pending_tasks)
        for category_id in ordered_group_ids(list(grouped_tasks.keys()), self.categories):
            group_tasks = grouped_tasks[category_id]
            self.taskGroupsLayout.addWidget(self._pending_group(category_id, group_tasks))

        self.taskGroupsLayout.addStretch(1)

    def _pending_group(self, category_id: str, group_tasks: list[TaskRecord]) -> QFrame:
        category = get_category(self.categories, category_id)
        color = safe_color(category.get("color"))
        text_color = readable_color(color)
        is_collapsed = category_id in self.collapsed_categories

        group = PendingGroupFrame(color)
        group.setObjectName("pendingGroup")
        group.setStyleSheet(
            f"""
            QToolButton {{
                color: {text_color};
                background: transparent;
                border: none;
                font-size: 16px;
                font-weight: 700;
                padding: 0;
                text-align: left;
            }}
            """
        )
        layout = QVBoxLayout(group)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header_row = QWidget()
        header_layout = QHBoxLayout(header_row)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        title_button = QToolButton()
        title_button.setObjectName("groupHeaderButton")
        title_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        title_button.setIcon(material_icon(str(category.get("icon", "label")), text_color, 20))
        title_button.setIconSize(icon_size(20))
        title_button.setText(f"{category.get('name', 'Sin categoría')} ({len(group_tasks)})")
        title_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        title_button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        title_button.clicked.connect(lambda checked=False, cat_id=category_id: self.toggle_pending_group(cat_id))

        expand_button = QToolButton()
        expand_button.setObjectName("groupExpandButton")
        expand_button.setIcon(material_icon("chevron_right" if is_collapsed else "expand_more", text_color, 20))
        expand_button.setIconSize(icon_size(20))
        expand_button.setFixedSize(28, 28)
        expand_button.setToolTip("Contraer o expandir")
        expand_button.clicked.connect(lambda checked=False, cat_id=category_id: self.toggle_pending_group(cat_id))

        header_layout.addWidget(title_button, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header_layout.addStretch(1)
        header_layout.addWidget(expand_button, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(header_row)

        if not is_collapsed:
            for task in group_tasks:
                layout.addWidget(self._task_card(task, color))

        return group

    def _task_drag_placeholder(self) -> QFrame:
        placeholder = TaskDragPlaceholder(self)
        placeholder.setObjectName("taskDragPlaceholder")
        placeholder.setFixedHeight(max(TASK_DRAG_PLACEHOLDER_MIN_HEIGHT, self.task_drag_placeholder_height))
        placeholder.setStyleSheet(
            """
            QFrame#taskDragPlaceholder {
                background-color: rgba(115, 90, 59, 18);
                border: 1px dashed rgba(115, 90, 59, 95);
                border-radius: 10px;
            }
            """
        )
        return placeholder

    def _task_card(self, task: TaskRecord, color: str) -> QFrame:
        task_id = str(task.get("id", ""))
        category_id = str(task.get("categoryId", ""))
        card = ReorderDropFrame(self, DRAG_KIND_TASK, task_id, category_id)
        card.setObjectName("taskCard")
        card.setStyleSheet(
            f"""
            QFrame#taskCard {{
                background-color: #ffffff;
                border-left: 2px solid transparent;
                border-radius: 10px;
            }}
            QFrame#taskCard:hover {{
                border-left: 2px solid {qss_rgba(color, 0.45)};
            }}
            """
        )

        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 12, 12, 12)
        layout.setSpacing(12)

        complete_button = QPushButton("")
        complete_button.setObjectName("completeTaskButton")
        complete_button.setIcon(material_icon("check", "#735a3b", 14))
        complete_button.setIconSize(icon_size(14))
        complete_button.setToolTip("Marcar como completada")
        complete_button.setFixedSize(22, 22)
        complete_button.clicked.connect(
            lambda checked=False, task_id=str(task.get("id", "")): self.toggle_task_complete(task_id, True)
        )

        title = QLabel(str(task.get("title", "")))
        title.setWordWrap(True)
        title.setObjectName("taskTitleLabel")
        title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        priority = QComboBox()
        priority.setObjectName("taskCardPriorityCombo")
        priority.setToolTip("Editar prioridad")
        priority.setIconSize(icon_size(14))
        for priority_name in PRIORITIES:
            priority.addItem(material_icon("flag", priority_color(priority_name), 14), priority_name, priority_name)
        current_priority = str(task.get("priority", DEFAULT_PRIORITY))
        priority.setCurrentIndex(max(0, priority.findData(current_priority)))
        priority.currentIndexChanged.connect(
            lambda index, combo=priority, task_id=task_id: self.update_task_priority(
                task_id,
                str(combo.itemData(index) or DEFAULT_PRIORITY),
            )
        )

        delete_button = QPushButton("")
        delete_button.setObjectName("deleteTaskButton")
        delete_button.setIcon(material_icon("delete", "#80756b", 18))
        delete_button.setIconSize(icon_size(18))
        delete_button.setToolTip("Eliminar tarea")
        delete_button.setFixedSize(34, 34)
        delete_button.clicked.connect(
            lambda checked=False, task_id=str(task.get("id", "")): self.delete_task(task_id)
        )

        layout.addWidget(DragHandle(self, DRAG_KIND_TASK, task_id, category_id))
        layout.addWidget(complete_button)
        layout.addWidget(title, 1)
        layout.addWidget(priority)
        layout.addWidget(delete_button)
        return card

    def render_stats(self) -> None:
        completed_tasks = [task for task in self.tasks if task.get("completed")]
        counts = {
            "hoy": sum(is_date_in_range(task.get("completedAt"), "hoy") for task in completed_tasks),
            "semana": sum(is_date_in_range(task.get("completedAt"), "semana") for task in completed_tasks),
            "mes": sum(is_date_in_range(task.get("completedAt"), "mes") for task in completed_tasks),
        }

        self.statHoyLabel.setText(str(counts["hoy"]))
        self.statSemanaLabel.setText(str(counts["semana"]))
        self.statMesLabel.setText(str(counts["mes"]))

        clear_layout(self.completedGroupsLayout)
        filtered_tasks = [
            task
            for task in completed_tasks
            if is_date_in_range(task.get("completedAt"), self.current_stat_filter)
        ]

        if not filtered_tasks:
            self.completedGroupsLayout.addWidget(
                self._empty_card("No hay tareas completadas en este periodo.", compact=True, icon_name="done_all")
            )
            self.completedGroupsLayout.addStretch(1)
            return

        all_completed_groups = grouped_by_category(completed_tasks)
        self.completed_category_order = normalize_completed_category_order(
            self.completed_category_order,
            list(all_completed_groups.keys()),
            self.categories,
        )
        grouped_tasks = grouped_by_category(filtered_tasks)
        for category_id in ordered_group_ids(list(grouped_tasks.keys()), self.categories, self.completed_category_order):
            group_tasks = grouped_tasks[category_id]
            self.completedGroupsLayout.addWidget(self._completed_group(category_id, group_tasks))

        self.completedGroupsLayout.addStretch(1)

    def _completed_group(self, category_id: str, group_tasks: list[TaskRecord]) -> QFrame:
        category = get_category(self.categories, category_id)
        color = safe_color(category.get("color"))
        text_color = readable_color(color)
        is_collapsed = category_id in self.collapsed_completed_categories

        group = ReorderDropFrame(self, DRAG_KIND_COMPLETED_CATEGORY, category_id)
        group.setObjectName("completedGroup")
        group.setStyleSheet(
            f"""
            QFrame#completedGroup {{
                background-color: transparent;
                border: none;
            }}
            QToolButton {{
                color: #4e453c;
                background-color: transparent;
                border: none;
                border-radius: 7px;
                font-size: 13px;
                font-weight: 700;
                padding: 5px;
                text-align: left;
            }}
            QToolButton:hover {{
                background-color: #efeeea;
            }}
            """
        )
        layout = QVBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header_row = QWidget()
        header_layout = QHBoxLayout(header_row)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        header = QToolButton()
        header.setObjectName("completedGroupHeaderButton")
        header.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        header.setIcon(material_icon(str(category.get("icon", "label")), text_color, 16))
        header.setIconSize(icon_size(16))
        header.setText(f"{category.get('name', 'Sin categoría')}   {len(group_tasks)}")
        header.setStyleSheet(
            f"""
            QToolButton {{
                color: {text_color};
                background-color: transparent;
                border: none;
                border-radius: 7px;
                font-size: 13px;
                font-weight: 700;
                padding: 5px;
                text-align: left;
            }}
            QToolButton:hover {{
                background-color: #efeeea;
            }}
            """
        )
        header.clicked.connect(lambda checked=False, cat_id=category_id: self.toggle_completed_group(cat_id))

        expand_button = QToolButton()
        expand_button.setObjectName("completedGroupExpandButton")
        expand_button.setIcon(material_icon("chevron_right" if is_collapsed else "expand_more", text_color, 16))
        expand_button.setIconSize(icon_size(16))
        expand_button.setFixedSize(24, 24)
        expand_button.setToolTip("Contraer o expandir")
        expand_button.clicked.connect(lambda checked=False, cat_id=category_id: self.toggle_completed_group(cat_id))

        header_layout.addWidget(DragHandle(self, DRAG_KIND_COMPLETED_CATEGORY, category_id))
        header_layout.addWidget(header, 1)
        header_layout.addWidget(expand_button)
        layout.addWidget(header_row)

        if not is_collapsed:
            list_frame = QFrame()
            list_frame.setObjectName("completedTaskList")
            list_frame.setStyleSheet(
                f"""
                QFrame#completedTaskList {{
                    border-left: 1px solid {qss_rgba(color, 0.32)};
                    margin-left: 8px;
                }}
                """
            )
            list_layout = QVBoxLayout(list_frame)
            list_layout.setContentsMargins(12, 2, 0, 8)
            list_layout.setSpacing(4)
            for task in group_tasks:
                list_layout.addWidget(self._completed_task_row(task))
            layout.addWidget(list_frame)

        return group

    def _completed_task_row(self, task: TaskRecord) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel(str(task.get("title", "")))
        title.setObjectName("completedTaskTitle")
        title.setWordWrap(True)
        title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        restore_button = QPushButton("Restaurar")
        restore_button.setObjectName("restoreTaskButton")
        restore_button.setIcon(material_icon("undo", "#735a3b", 14))
        restore_button.setIconSize(icon_size(14))
        restore_button.clicked.connect(
            lambda checked=False, task_id=str(task.get("id", "")): self.toggle_task_complete(task_id, False)
        )

        layout.addWidget(title, 1)
        layout.addWidget(restore_button)
        return row

    def _empty_card(self, text: str, compact: bool = False, icon_name: str | None = None) -> QFrame:
        card = QFrame()
        card.setObjectName("emptyCard")
        layout = QVBoxLayout(card)
        margins = 12 if compact else 28
        layout.setContentsMargins(margins, margins, margins, margins)
        if icon_name:
            icon = QLabel()
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon.setPixmap(material_pixmap(icon_name, "#d1c4b8", 44 if not compact else 24))
            layout.addWidget(icon)
        label = QLabel(text)
        label.setObjectName("emptyStateLabel")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        layout.addWidget(label)
        return card

    def pick_category_color(self) -> None:
        color = QColorDialog.getColor(QColor(self.selected_category_color), self, "Elegir color")
        if color.isValid():
            self._set_category_color(color.name())

    def _set_category_color(self, color: str) -> None:
        self.selected_category_color = safe_color(color)
        self.categoryColorButton.setStyleSheet(
            f"""
            QPushButton#categoryColorButton {{
                background-color: {self.selected_category_color};
                border: 3px solid #ffffff;
                border-radius: 21px;
            }}
            QPushButton#categoryColorButton:hover {{
                border-color: #d1c4b8;
            }}
            """
        )

    def add_category(self) -> None:
        name = self.categoryNameEdit.text().strip()
        if not name:
            return

        category = {
            "id": self._new_id("cat", [str(item.get("id", "")) for item in self.categories]),
            "name": name,
            "color": self.selected_category_color,
            "icon": self.categoryIconCombo.currentData() or "label",
        }
        self.categories.append(category)
        self.categoryNameEdit.clear()
        self.categoryIconCombo.setCurrentIndex(0)
        self._set_category_color("#68abff")

        self.render_categories()
        self.update_category_select()
        self._save()

    def delete_category(self, category_id: str) -> None:
        if any(task.get("categoryId") == category_id for task in self.tasks):
            QMessageBox.warning(
                self,
                "Categoría en uso",
                "No puedes eliminar una categoría que está siendo usada por tareas.",
            )
            return

        self.categories = [category for category in self.categories if category.get("id") != category_id]
        self.collapsed_categories.discard(category_id)
        self.collapsed_completed_categories.discard(category_id)
        self.completed_category_order = [item_id for item_id in self.completed_category_order if item_id != category_id]
        self.render_categories()
        self.update_category_select()
        self.render_tasks()
        self.render_stats()
        self._save()

    def add_task(self) -> None:
        title = self.taskTitleEdit.text().strip()
        category_id = self.taskCategoryCombo.currentData()
        priority = self.taskPriorityCombo.currentData() or DEFAULT_PRIORITY
        if not title or not category_id:
            return

        task = {
            "id": self._new_id("task", [str(item.get("id", "")) for item in self.tasks]),
            "title": title,
            "categoryId": category_id,
            "priority": priority,
            "completed": False,
        }
        self.tasks.append(task)
        self.taskTitleEdit.clear()
        self.collapsed_categories.discard(str(category_id))
        self.render_tasks()
        self._save()

    def toggle_task_complete(self, task_id: str, is_completed: bool) -> None:
        task = self._find_task(task_id)
        if task is None:
            return

        task["completed"] = is_completed
        if is_completed:
            task["completedAt"] = utc_now_iso()
        else:
            task.pop("completedAt", None)

        self.render_tasks()
        self.render_stats()
        self._save()

    def delete_task(self, task_id: str) -> None:
        self.tasks = [task for task in self.tasks if task.get("id") != task_id]
        self.render_tasks()
        self.render_stats()
        self._save()

    def update_task_priority(self, task_id: str, priority: str) -> None:
        if priority not in PRIORITIES:
            priority = DEFAULT_PRIORITY
        task = self._find_task(task_id)
        if task is None or task.get("priority") == priority:
            return

        task["priority"] = priority
        self.render_tasks()
        self._save()

    def can_drop_reorder(
        self,
        drag_kind: str,
        moved_id: str,
        moved_category_id: str,
        target_id: str,
        target_category_id: str,
    ) -> bool:
        if moved_id == target_id:
            return False
        if drag_kind == DRAG_KIND_CATEGORY:
            return self._has_category(moved_id) and self._has_category(target_id)
        if drag_kind == DRAG_KIND_COMPLETED_CATEGORY:
            return moved_id in self.completed_category_order and target_id in self.completed_category_order
        if drag_kind == DRAG_KIND_TASK:
            return (
                moved_category_id == target_category_id
                and self._is_pending_task_in_category(moved_id, moved_category_id)
                and self._is_pending_task_in_category(target_id, target_category_id)
            )
        return False

    def handle_reorder_drop(
        self,
        drag_kind: str,
        moved_id: str,
        moved_category_id: str,
        target_id: str,
        target_category_id: str,
    ) -> bool:
        if not self.can_drop_reorder(drag_kind, moved_id, moved_category_id, target_id, target_category_id):
            return False

        if drag_kind == DRAG_KIND_CATEGORY:
            self.categories = reorder_records_by_id(self.categories, moved_id, target_id)
            self.render_categories()
            self.update_category_select()
            self.render_tasks()
            self.render_stats()
        elif drag_kind == DRAG_KIND_COMPLETED_CATEGORY:
            self.completed_category_order = reorder_string_ids(self.completed_category_order, moved_id, target_id)
            self.render_stats()
        elif drag_kind == DRAG_KIND_TASK:
            self.tasks = reorder_pending_tasks_within_category(self.tasks, moved_category_id, moved_id, target_id)
            self.render_tasks()
        else:
            return False

        self._save()
        return True

    def begin_task_drag(self, task_id: str, category_id: str, source_card: QWidget | None) -> None:
        if self.dragging_task_id is not None:
            self.clear_task_drag_preview()

        self.dragging_task_id = task_id
        self.dragging_task_category_id = category_id
        self.task_drag_preview_category_id = None
        self.task_drag_preview_index = None
        if source_card is not None:
            self.task_drag_placeholder_height = max(
                TASK_DRAG_PLACEHOLDER_MIN_HEIGHT,
                source_card.height() or source_card.sizeHint().height(),
            )
        else:
            self.task_drag_placeholder_height = TASK_DRAG_PLACEHOLDER_MIN_HEIGHT

        self.task_drag_source_card = source_card
        self.task_drag_placeholder = self._task_drag_placeholder()
        if source_card is not None:
            layout = self._task_layout_for_widget(source_card)
            if layout is not None:
                source_index = layout.indexOf(source_card)
                if source_index >= 0:
                    layout.insertWidget(source_index, self.task_drag_placeholder)
                    source_card.hide()

    def end_task_drag(self) -> None:
        if self.dragging_task_id is None and self.task_drag_preview_index is None and self.task_drag_source_card is None:
            return
        self.clear_task_drag_preview()

    def clear_task_drag_preview(self, *, render: bool = True) -> None:
        placeholder = self.task_drag_placeholder
        if placeholder is not None:
            layout = self._task_layout_for_widget(placeholder)
            if layout is not None:
                layout.removeWidget(placeholder)
            placeholder.deleteLater()

        if self.task_drag_source_card is not None:
            self.task_drag_source_card.show()

        self.dragging_task_id = None
        self.dragging_task_category_id = None
        self.task_drag_preview_category_id = None
        self.task_drag_preview_index = None
        self.task_drag_placeholder_height = TASK_DRAG_PLACEHOLDER_MIN_HEIGHT
        self.task_drag_source_card = None
        self.task_drag_placeholder = None
        if render:
            self.taskGroupsWidget.updateGeometry()
            self.taskGroupsWidget.update()

    def preview_task_reorder(
        self,
        moved_id: str,
        moved_category_id: str,
        target_id: str,
        target_category_id: str,
        drop_after: bool,
    ) -> bool:
        insertion_index = self.task_reorder_insertion_index(
            moved_id,
            moved_category_id,
            target_id,
            target_category_id,
            drop_after,
        )
        if insertion_index is None:
            return False

        if (
            self.task_drag_preview_category_id == moved_category_id
            and self.task_drag_preview_index == insertion_index
        ):
            return True

        self.task_drag_preview_category_id = moved_category_id
        self.task_drag_preview_index = insertion_index
        self.move_task_drag_placeholder(target_id, drop_after)
        return True

    def can_drop_task_reorder_preview(self, moved_id: str, moved_category_id: str) -> bool:
        return (
            self.dragging_task_id == moved_id
            and self.dragging_task_category_id == moved_category_id
            and self.task_drag_preview_category_id == moved_category_id
            and self.task_drag_preview_index is not None
            and self._is_pending_task_in_category(moved_id, moved_category_id)
        )

    def handle_task_reorder_preview_drop(self, moved_id: str, moved_category_id: str) -> bool:
        if not self.can_drop_task_reorder_preview(moved_id, moved_category_id):
            return False
        return self.apply_task_reorder_at_index(
            moved_id,
            moved_category_id,
            self.task_drag_preview_index,
        )

    def handle_task_reorder_drop(
        self,
        moved_id: str,
        moved_category_id: str,
        target_id: str,
        target_category_id: str,
        drop_after: bool,
    ) -> bool:
        insertion_index = self.task_reorder_insertion_index(
            moved_id,
            moved_category_id,
            target_id,
            target_category_id,
            drop_after,
        )
        if insertion_index is None:
            return False

        return self.apply_task_reorder_at_index(moved_id, moved_category_id, insertion_index)

    def apply_task_reorder_at_index(
        self,
        moved_id: str,
        moved_category_id: str,
        insertion_index: int,
    ) -> bool:
        visual_insertion_index = self.task_drag_visual_insertion_index(moved_category_id)
        if visual_insertion_index is not None:
            insertion_index = visual_insertion_index

        reordered_tasks = reorder_pending_tasks_within_category_at_index(
            self.tasks,
            moved_category_id,
            moved_id,
            insertion_index,
        )
        if reordered_tasks == self.tasks:
            self.clear_task_drag_preview(render=False)
            self.finish_task_reorder_without_refresh()
            return False

        self.tasks = reordered_tasks
        if not self.finish_task_reorder_without_refresh():
            self.clear_task_drag_preview(render=False)
            self.render_tasks_preserving_pending_scroll()
        self._save()
        return True

    def finish_task_reorder_without_refresh(self) -> bool:
        placeholder = self.task_drag_placeholder
        source_card = self.task_drag_source_card
        if placeholder is None or source_card is None:
            return False

        layout = self._task_layout_for_widget(placeholder)
        if layout is None:
            return False

        placeholder_index = layout.indexOf(placeholder)
        if placeholder_index < 0:
            return False

        current_source_layout = self._task_layout_for_widget(source_card)
        source_index = current_source_layout.indexOf(source_card) if current_source_layout is layout else -1
        insert_index = placeholder_index - 1 if 0 <= source_index < placeholder_index else placeholder_index

        layout.removeWidget(placeholder)
        placeholder.deleteLater()

        if current_source_layout is not None:
            current_source_layout.removeWidget(source_card)

        layout.insertWidget(insert_index, source_card)
        source_card.show()

        self.dragging_task_id = None
        self.dragging_task_category_id = None
        self.task_drag_preview_category_id = None
        self.task_drag_preview_index = None
        self.task_drag_placeholder_height = TASK_DRAG_PLACEHOLDER_MIN_HEIGHT
        self.task_drag_source_card = None
        self.task_drag_placeholder = None
        self.taskGroupsWidget.updateGeometry()
        self.taskGroupsWidget.update()
        return True

    def task_drag_visual_insertion_index(self, category_id: str) -> int | None:
        placeholder = self.task_drag_placeholder
        moved_id = self.dragging_task_id
        if placeholder is None or moved_id is None:
            return None

        layout = self._task_layout_for_widget(placeholder)
        if layout is None:
            return None

        placeholder_index = layout.indexOf(placeholder)
        if placeholder_index < 0:
            return None

        insertion_index = 0
        for index in range(placeholder_index):
            item = layout.itemAt(index)
            if item is None:
                continue
            widget = item.widget()
            if not isinstance(widget, ReorderDropFrame):
                continue
            if widget.drag_kind != DRAG_KIND_TASK or widget.isHidden():
                continue
            if widget.target_category_id != category_id or widget.target_id == moved_id:
                continue
            insertion_index += 1
        return insertion_index

    def render_tasks_preserving_pending_scroll(self) -> None:
        scrollbar = self.pendingTasksScroll.verticalScrollBar()
        scroll_value = scrollbar.value()
        self.pendingTasksScroll.setUpdatesEnabled(False)
        self.taskGroupsWidget.setUpdatesEnabled(False)
        try:
            self.render_tasks()
        finally:
            self.taskGroupsWidget.setUpdatesEnabled(True)
            self.pendingTasksScroll.setUpdatesEnabled(True)
        QTimer.singleShot(0, lambda: scrollbar.setValue(min(scroll_value, scrollbar.maximum())))

    def move_task_drag_placeholder(self, target_id: str, drop_after: bool) -> None:
        placeholder = self.task_drag_placeholder
        if placeholder is None:
            return

        target_card = self._find_visible_task_card(target_id)
        if target_card is None:
            return

        layout = self._task_layout_for_widget(target_card)
        if layout is None:
            return

        layout.removeWidget(placeholder)
        target_index = layout.indexOf(target_card)
        if target_index < 0:
            return
        layout.insertWidget(target_index + (1 if drop_after else 0), placeholder)

    def _find_visible_task_card(self, task_id: str) -> ReorderDropFrame | None:
        for card in self.findChildren(ReorderDropFrame):
            if (
                card.drag_kind == DRAG_KIND_TASK
                and card.target_id == task_id
                and not card.isHidden()
            ):
                return card
        return None

    @staticmethod
    def _task_layout_for_widget(widget: QWidget) -> QLayout | None:
        parent = widget.parentWidget()
        if parent is None:
            return None
        layout = parent.layout()
        return layout if isinstance(layout, QVBoxLayout) else None

    def task_reorder_insertion_index(
        self,
        moved_id: str,
        moved_category_id: str,
        target_id: str,
        target_category_id: str,
        drop_after: bool,
    ) -> int | None:
        if moved_id == target_id or moved_category_id != target_category_id:
            return None
        if not self._is_pending_task_in_category(moved_id, moved_category_id):
            return None
        if not self._is_pending_task_in_category(target_id, target_category_id):
            return None

        visible_tasks = [
            task
            for task in self.tasks
            if (
                not task.get("completed")
                and str(task.get("categoryId", "")) == moved_category_id
                and str(task.get("id", "")) != moved_id
            )
        ]
        for index, task in enumerate(visible_tasks):
            if str(task.get("id", "")) == target_id:
                return index + (1 if drop_after else 0)
        return None

    def toggle_pending_group(self, category_id: str) -> None:
        toggle_set_member(self.collapsed_categories, category_id)
        self.render_tasks()

    def toggle_completed_group(self, category_id: str) -> None:
        toggle_set_member(self.collapsed_completed_categories, category_id)
        self.render_stats()

    def set_stat_filter(self, stat_filter: str) -> None:
        self.current_stat_filter = stat_filter
        self._update_filter_buttons()
        self.render_stats()

    def _update_filter_buttons(self) -> None:
        buttons = {
            "hoy": self.filterTodayButton,
            "semana": self.filterWeekButton,
            "mes": self.filterMonthButton,
        }
        for key, button in buttons.items():
            is_active = key == self.current_stat_filter
            button.setChecked(is_active)
            button.setProperty("filterActive", is_active)
            repolish(button)

    def _find_task(self, task_id: str) -> TaskRecord | None:
        for task in self.tasks:
            if task.get("id") == task_id:
                return task
        return None

    def _has_category(self, category_id: str) -> bool:
        return any(category.get("id") == category_id for category in self.categories)

    def _is_pending_task_in_category(self, task_id: str, category_id: str) -> bool:
        task = self._find_task(task_id)
        return bool(task and not task.get("completed") and str(task.get("categoryId", "")) == category_id)

    def _save(self) -> None:
        try:
            self.store.save(
                {
                    "tasks": self.tasks,
                    "categories": self.categories,
                    "completedCategoryOrder": self.completed_category_order,
                }
            )
        except OSError as exc:
            QMessageBox.critical(self, "Error guardando datos", str(exc))

    @staticmethod
    def _new_id(prefix: str, existing_ids: list[str]) -> str:
        existing = set(existing_ids)
        timestamp = int(time.time() * 1000)
        new_id = f"{prefix}-{timestamp}"
        while new_id in existing:
            timestamp += 1
            new_id = f"{prefix}-{timestamp}"
        return new_id


def grouped_by_category(tasks: list[TaskRecord]) -> OrderedDict[str, list[TaskRecord]]:
    grouped: OrderedDict[str, list[TaskRecord]] = OrderedDict()
    for task in tasks:
        category_id = str(task.get("categoryId", ""))
        grouped.setdefault(category_id, []).append(task)
    return grouped


def reorder_string_ids(values: list[str], moved_id: str, target_id: str) -> list[str]:
    if moved_id == target_id or moved_id not in values or target_id not in values:
        return values[:]
    reordered = values[:]
    reordered.remove(moved_id)
    reordered.insert(reordered.index(target_id), moved_id)
    return reordered


def clear_layout(layout: QGridLayout | QVBoxLayout | QHBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child_layout is not None:
            clear_layout(child_layout)


def toggle_set_member(values: set[str], value: str) -> None:
    if value in values:
        values.remove(value)
    else:
        values.add(value)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def is_date_in_range(date_string: Any, date_range: str) -> bool:
    if not date_string:
        return False
    try:
        raw = str(date_string)
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone()
        completed_date = parsed.date()
    except ValueError:
        return False

    today = datetime.now().date()
    diff_days = abs((today - completed_date).days)
    if date_range == "hoy":
        return diff_days == 0
    if date_range == "semana":
        return diff_days <= 7
    if date_range == "mes":
        return diff_days <= 30
    return False


def safe_color(value: Any) -> str:
    if not isinstance(value, str):
        return "#8b7d6b"
    color = value.strip()
    if len(color) == 7 and color.startswith("#"):
        try:
            int(color[1:], 16)
            return color.lower()
        except ValueError:
            return "#8b7d6b"
    return "#8b7d6b"


def qss_rgba(hex_color: str, alpha: float) -> str:
    color = safe_color(hex_color)
    red = int(color[1:3], 16)
    green = int(color[3:5], 16)
    blue = int(color[5:7], 16)
    alpha_value = max(0, min(255, round(alpha * 255)))
    return f"rgba({red}, {green}, {blue}, {alpha_value})"


def readable_color(hex_color: str) -> str:
    color = safe_color(hex_color)
    red = int(color[1:3], 16)
    green = int(color[3:5], 16)
    blue = int(color[5:7], 16)
    luminance = (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255
    return "#4e453c" if luminance > 0.72 else color


def priority_color(priority: str) -> str:
    colors = {
        "Alta": "#ba1a1a",
        "Media": "#735a3b",
        "Baja": "#0060ac",
    }
    return colors.get(priority, colors[DEFAULT_PRIORITY])


def priority_style(priority: str) -> str:
    styles = {
        "Alta": ("#ffdad6", "#ba1a1a"),
        "Media": ("#eadcca", "#735a3b"),
        "Baja": ("#d4e3ff", "#0060ac"),
    }
    background, foreground = styles.get(priority, styles[DEFAULT_PRIORITY])
    return f"""
        QLabel#priorityBadge {{
            background-color: {background};
            color: {foreground};
            border-radius: 5px;
            padding: 3px 8px;
            font-size: 10px;
            font-weight: 800;
            text-transform: uppercase;
        }}
    """


def repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


APP_STYLES = """
QMainWindow,
QWidget#centralwidget,
QWidget#dashboardWidget {
    background-color: #fbf9f5;
    color: #1b1c1a;
    font-family: "Plus Jakarta Sans", "Inter", "Segoe UI", sans-serif;
}

QFrame#topBar {
    background-color: #fbf9f5;
}

QLabel#appTitleLabel {
    color: #735a3b;
    font-size: 24px;
    font-weight: 800;
}

QLabel#categoriesTitleLabel,
QLabel#statsTitleLabel {
    color: #735a3b;
    font-size: 18px;
    font-weight: 700;
}

QLabel#newCategoryLabel {
    color: #4e453c;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
}

QFrame#leftPanel,
QFrame#rightPanel {
    background-color: #f5f3ef;
    border-radius: 12px;
}

QFrame#categoryListSeparator {
    background-color: rgba(209, 196, 184, 90);
    border: none;
}

QFrame#taskFormCard {
    background-color: #fbf9f5;
    border: 1px solid rgba(209, 196, 184, 45);
    border-radius: 12px;
}

QFrame#todayStatsCard,
QFrame#weekStatsCard,
QFrame#monthStatsCard,
QFrame#completedHistoryCard {
    background-color: #ffffff;
    border: 1px solid rgba(209, 196, 184, 45);
    border-radius: 12px;
}

QLabel#todayStatsTitle,
QLabel#weekStatsTitle,
QLabel#monthStatsTitle {
    color: #4e453c;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
}

QLabel#statHoyLabel,
QLabel#statSemanaLabel,
QLabel#statMesLabel {
    color: #735a3b;
    font-size: 30px;
    font-weight: 800;
}

QLabel#completedHistoryTitleLabel {
    color: #1b1c1a;
    font-size: 14px;
    font-weight: 700;
}

QLabel#dragHandle {
    color: #a99a8d;
    font-size: 12px;
    font-weight: 800;
}

QLabel#dragHandle:hover {
    color: #735a3b;
}

QLineEdit,
QComboBox {
    background-color: #e4e2de;
    color: #1b1c1a;
    border: none;
    border-radius: 8px;
    padding: 9px 12px;
    font-size: 14px;
}

QComboBox#categoryIconCombo {
    padding: 8px 6px;
}

QComboBox#categoryIconCombo:focus {
    background-color: #e4e2de;
    border: none;
}

QComboBox#categoryIconCombo::drop-down {
    border: none;
    width: 14px;
}

QComboBox#taskCategoryCombo,
QComboBox#taskPriorityCombo {
    background-color: #e4e2de;
    color: #1b1c1a;
    border: none;
    border-radius: 17px;
    padding: 9px 30px 9px 16px;
}

QComboBox#taskCardPriorityCombo {
    background-color: #f1eee8;
    color: #4e453c;
    border: none;
    border-radius: 7px;
    padding: 4px 22px 4px 8px;
    font-size: 11px;
    font-weight: 800;
    min-width: 92px;
}

QComboBox#taskCardPriorityCombo:hover {
    background-color: #e4e2de;
}

QComboBox#taskCardPriorityCombo::drop-down {
    border: none;
    width: 20px;
}

QComboBox#taskCardPriorityCombo QAbstractItemView {
    background-color: #fbf9f5;
    color: #1b1c1a;
    border: 1px solid #d1c4b8;
    border-radius: 8px;
    padding: 4px;
    outline: 0;
    selection-background-color: #eee7df;
    selection-color: #1b1c1a;
}

QComboBox#taskCategoryCombo:hover,
QComboBox#taskPriorityCombo:hover {
    background-color: #d8d4ce;
}

QComboBox#taskCategoryCombo:focus,
QComboBox#taskPriorityCombo:focus {
    background-color: #e4e2de;
    border: 1px solid #d1c4b8;
    padding: 8px 29px 8px 15px;
}

QComboBox#taskCategoryCombo::drop-down,
QComboBox#taskPriorityCombo::drop-down {
    border: none;
    width: 24px;
}

QComboBox#taskCategoryCombo::down-arrow,
QComboBox#taskPriorityCombo::down-arrow {
    width: 12px;
    height: 12px;
}

QComboBox#taskCategoryCombo QAbstractItemView,
QComboBox#taskPriorityCombo QAbstractItemView {
    background-color: #fbf9f5;
    color: #1b1c1a;
    border: 1px solid #d1c4b8;
    border-radius: 8px;
    padding: 4px;
    outline: 0;
    selection-background-color: #eee7df;
    selection-color: #1b1c1a;
}

QListView#categoryIconGridPopup {
    background-color: #fbf9f5;
    border: 1px solid #d1c4b8;
    border-radius: 8px;
    padding: 4px;
    outline: 0;
}

QListView#categoryIconGridPopup::item {
    border-radius: 7px;
    padding: 8px;
}

QListView#categoryIconGridPopup::item:hover {
    background-color: #eee7df;
}

QListView#categoryIconGridPopup::item:selected {
    background-color: #d4e3ff;
}

QLineEdit#taskTitleEdit {
    background: transparent;
    color: #1b1c1a;
    font-size: 20px;
    font-weight: 600;
    padding: 8px 0;
}

QLineEdit:focus,
QComboBox:focus {
    background-color: #ffffff;
    border: 1px solid #d1c4b8;
}

QPushButton {
    border: none;
    border-radius: 8px;
    padding: 8px 13px;
    font-weight: 700;
}

QPushButton#addTaskButton {
    background-color: #735a3b;
    color: #ffffff;
    border-radius: 17px;
    padding: 9px 20px;
}

QPushButton#addCategoryButton {
    background-color: #e4e2de;
    color: #735a3b;
    border-radius: 17px;
}

QPushButton#addTaskButton:hover,
QPushButton#addCategoryButton:hover {
    background-color: #806642;
    color: #ffffff;
}

QPushButton#filterTodayButton,
QPushButton#filterWeekButton,
QPushButton#filterMonthButton {
    background-color: #eae8e4;
    color: #4e453c;
    border-radius: 7px;
    padding: 7px 8px;
    font-size: 12px;
}

QPushButton[filterActive="true"] {
    background-color: #ffffff;
    color: #735a3b;
    border: 1px solid rgba(209, 196, 184, 70);
}

QPushButton#completeTaskButton {
    background-color: #ffffff;
    border: 2px solid #d1c4b8;
    border-radius: 6px;
    padding: 0;
}

QPushButton#completeTaskButton:hover {
    border-color: #735a3b;
    background-color: #ffddb8;
}

QPushButton#deleteTaskButton {
    background-color: transparent;
    color: #80756b;
    padding: 5px 8px;
}

QPushButton#deleteTaskButton:hover {
    background-color: #ffdad6;
    color: #ba1a1a;
}

QPushButton#restoreTaskButton {
    background-color: transparent;
    color: #735a3b;
    padding: 3px 4px;
    font-size: 12px;
}

QPushButton#restoreTaskButton:hover {
    text-decoration: underline;
}

QLabel#taskTitleLabel {
    color: #1b1c1a;
    font-size: 15px;
    font-weight: 600;
}

QLabel#completedTaskTitle {
    color: rgba(78, 69, 60, 190);
    font-size: 12px;
    text-decoration: line-through;
}

QFrame#emptyCard {
    background-color: #f5f3ef;
    border-radius: 12px;
}

QLabel#emptyStateLabel {
    color: #4e453c;
    font-size: 14px;
    font-weight: 600;
}

QScrollArea {
    background: transparent;
    border: none;
}

QScrollBar:vertical {
    background: #eee9e3;
    border: none;
    border-radius: 4px;
    width: 8px;
    margin: 0;
}

QScrollBar::groove:vertical {
    background: #eee9e3;
    border: none;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: #d1c4b8;
    border-radius: 4px;
    min-height: 24px;
}

QScrollBar::handle:vertical:hover {
    background: #80756b;
}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: transparent;
    border: none;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    background: transparent;
    border: none;
    height: 0px;
    width: 0px;
}

QScrollBar::up-arrow:vertical,
QScrollBar::down-arrow:vertical {
    background: transparent;
    border: none;
    height: 0px;
    width: 0px;
}
"""
