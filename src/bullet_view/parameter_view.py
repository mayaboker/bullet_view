"""Parameters tab widgets; protocol and file writes belong to the presenter."""
from PySide6 import QtCore, QtWidgets
from bullet_msgs.parameters import CATALOG, BY_ID
from .parameters import ParameterSnapshot, parse_edit

PARAMETER_NAME_WIDTH = 260
PARAMETER_VALUE_WIDTH = 130
PARAMETER_CATEGORY_WIDTH = 145
PARAMETER_DESCRIPTION_WIDTH = 360
PARAMETER_COLUMN_WIDTHS = {0: 42, 1: PARAMETER_NAME_WIDTH, 2: PARAMETER_VALUE_WIDTH,
    3: PARAMETER_CATEGORY_WIDTH, 4: PARAMETER_DESCRIPTION_WIDTH, 5: 85, 6: 100, 7: 130, 8: 75}
FAVORITES_SETTINGS_KEY = 'parameters/favorites'


class ParameterPanel(QtWidgets.QWidget):
    def __init__(self, presenter, *, settings=None):
        super().__init__()
        self.presenter = presenter
        self.settings = settings if settings is not None else QtCore.QSettings('Bullet', 'BulletView')
        self.favorites = set(self.settings.value(FAVORITES_SETTINGS_KEY, [], type=list))
        self.snapshot = ParameterSnapshot()
        self.mission_stopped = False
        self.rows = {}
        self.dirty = set()
        layout = QtWidgets.QVBoxLayout(self)
        controls = QtWidgets.QHBoxLayout()
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText('Search parameter name…')
        self.category = QtWidgets.QComboBox()
        self.category.addItems(['All categories', *sorted({p.category for p in CATALOG})])
        self.favorites_only = QtWidgets.QCheckBox('Favorites only')
        self.refresh = QtWidgets.QPushButton('Refresh')
        self.export = QtWidgets.QPushButton('Export YAML…')
        for widget in (self.search, self.category, self.favorites_only, self.refresh, self.export):
            controls.addWidget(widget)
        layout.addLayout(controls)
        self.progress = QtWidgets.QLabel('Waiting for Bullet heartbeat')
        layout.addWidget(self.progress)
        self.table = QtWidgets.QTableWidget(len(CATALOG), 9)
        self.table.setHorizontalHeaderLabels(['★', 'Parameter name', 'Value', 'Category', 'Description', 'Units', 'Editable', 'Status', ''])
        self.table.verticalHeader().hide()
        for column, width in PARAMETER_COLUMN_WIDTHS.items():
            self.table.setColumnWidth(column, width)
        self.table.horizontalHeader().setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        hint = QtWidgets.QLabel('Apply changes one row at a time. Selected gains update live; other fields require a stopped mission. '
                               'Changes are session-only. Export YAML to save a complete profile.')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        for row, p in enumerate(CATALOG):
            star = QtWidgets.QTableWidgetItem('★' if p.id in self.favorites else '☆')
            star.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
            star.setCheckState(QtCore.Qt.CheckState.Checked if p.id in self.favorites else QtCore.Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, star)
            for col, text in [(1,p.path), (3,p.category), (4,p.description), (5,p.units),
                              (6,'Live gain' if p.live else 'Stopped only'), (7,'Not loaded')]:
                item = QtWidgets.QTableWidgetItem(text)
                item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable)
                item.setToolTip(text)
                self.table.setItem(row, col, item)
            edit = QtWidgets.QLineEdit()
            edit.textEdited.connect(lambda text, id=p.id: self._edited(id))
            self.table.setCellWidget(row, 2, edit)
            apply = QtWidgets.QPushButton('Apply')
            apply.clicked.connect(lambda checked=False, id=p.id: self._apply(id))
            self.table.setCellWidget(row, 8, apply)
            self.rows[p.id] = (row, edit, apply)
        self.table.itemChanged.connect(self._favorite_changed)
        self.search.textChanged.connect(self._filter)
        self.category.currentTextChanged.connect(self._filter)
        self.favorites_only.toggled.connect(self._filter)
        self.refresh.clicked.connect(getattr(presenter, 'refresh_parameters', lambda: None))
        self.export.clicked.connect(self._export)
        if hasattr(presenter, 'parameters_changed'):
            presenter.parameters_changed.connect(self.set_parameters)
        presenter.snapshot_changed.connect(self._telemetry)
        self.set_parameters(self.snapshot)

    def _telemetry(self, snapshot):
        self.mission_stopped = snapshot.mission_stopped
        self._enable()

    def _edited(self, id):
        self.dirty.add(id)
        self._enable()

    def _favorite_changed(self, item):
        if item.column() != 0:
            return
        p = CATALOG[item.row()]
        if item.checkState() == QtCore.Qt.CheckState.Checked:
            self.favorites.add(p.id)
        else:
            self.favorites.discard(p.id)
        self.settings.setValue(FAVORITES_SETTINGS_KEY, sorted(self.favorites))
        self._filter()

    def _filter(self, *_):
        query = self.search.text().casefold()
        category = self.category.currentText()
        for p in CATALOG:
            hidden = (query not in p.path.casefold() or category not in ('All categories', p.category)
                      or self.favorites_only.isChecked() and p.id not in self.favorites)
            self.table.setRowHidden(self.rows[p.id][0], hidden)

    def _enable(self):
        ready = self.snapshot.online and self.snapshot.complete and not self.snapshot.pending
        in_flight = any(status == 'Pending' for _, status in self.snapshot.statuses)
        self.refresh.setEnabled(self.snapshot.online and not in_flight)
        self.export.setEnabled(ready)
        for p in CATALOG:
            _, edit, apply = self.rows[p.id]
            allowed = ready and (p.live or self.mission_stopped)
            edit.setEnabled(allowed)
            apply.setEnabled(allowed and p.id in self.dirty)

    def set_parameters(self, snapshot):
        self.snapshot = snapshot
        values, statuses = dict(snapshot.values), dict(snapshot.statuses)
        self.progress.setText(snapshot.progress)
        for p in CATALOG:
            row, edit, _ = self.rows[p.id]
            status = statuses.get(p.id, 'Loaded' if p.id in values else 'Not loaded')
            if status in ('Applied', 'Rejected', 'Confirmed by readback'):
                self.dirty.discard(p.id)
            if p.id in values and p.id not in self.dirty:
                value = values[p.id]
                edit.setText('null' if value is None else format(value, '.9g') if type(value) is float else str(value))
                edit.setToolTip('Confirmed value: ' + repr(value))
                edit.setCursorPosition(0)
            self.table.item(row, 7).setText(status)
            self.table.item(row, 7).setToolTip(status)
        self._enable()

    def _apply(self, id):
        row, edit, _ = self.rows[id]
        try:
            value = parse_edit(BY_ID[id], edit.text())
            self.presenter.apply_parameter(id, value)
        except (ValueError, OverflowError) as exc:
            self.table.item(row, 7).setText(str(exc))

    def _export(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Export confirmed mission profile', 'mission_profile.yaml', 'YAML (*.yaml *.yml)')
        if path:
            try:
                self.presenter.export_parameters(path)
            except (ValueError, OSError) as exc:
                QtWidgets.QMessageBox.warning(self, 'Export failed', str(exc))
