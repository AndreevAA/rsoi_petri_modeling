from PyQt5 import uic
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMainWindow, QFileDialog, QMessageBox, QDialog, QTabWidget
from editor.mode import ModeSwitch, Mode
from editor.simulationcontroller import SimulationController
from pathlib import Path

from editor.monitoring_widget import MonitoringWidget

from editor.monitoring_system import MonitoringSystem


class MainWindow(QMainWindow):
    def __init__(self, root_path: Path):
        """Инициализация главного окна приложения."""
        super().__init__()

        # Атрибут для хранения ссылки на окно конфигурации
        self.configure_dialog = None

        # Загрузка пользовательского интерфейса из .ui файла
        uic.loadUi(str((root_path / 'editor' / 'petnetsim.ui').resolve()), self)
        self.setWindowIcon(QIcon(str((root_path / 'editor' / 'pns_icon.svg').resolve())))

        # Инициализация свойств элементов интерфейса
        self.item_properties.after_init()
        self.item_properties.item_selected(None)

        # Подключение действий к методам
        self.actionSave.triggered.connect(self.save)
        self.actionSaveAs.triggered.connect(self.save_as)
        self.actionNew.triggered.connect(self.new)
        self.actionOpen.triggered.connect(self.open)

        self.filename = None  # Переменная для хранения имени файла

        # Инициализация контроллера симуляции и переключателя режима
        self.simulation_controller = SimulationController(self, self.editor)
        self.mode_switch = ModeSwitch(self)

        # Подключаем кнопку "Создать" к обработчику
        self.actionCreate.triggered.connect(self.open_configure_smo)

        # Инициализируем систему мониторинга и добавляем ее в контроллер
        self.simulation_controller.monitoring_system = MonitoringSystem(self.simulation_controller)

        # Создаем виджет мониторинга
        self.monitoring_widget = MonitoringWidget(self.simulation_controller.monitoring_system)

        # Проверяем, есть ли уже TabWidget, если нет - создаем его
        if not hasattr(self, 'tab_widget'):
            self.tab_widget = QTabWidget(self)
            # Добавляем TabWidget в основной интерфейс (центральный виджет)
            self.centralWidget().layout().addWidget(self.tab_widget)

        # Добавляем вкладку мониторинга
        self.tab_widget.addTab(self.monitoring_widget, "Мониторинг")

    def closeEvent(self, event):
        """Обработка закрытия главного окна"""
        # Останавливаем обновление мониторинга в реальном времени
        if hasattr(self, 'simulation_controller') and hasattr(self.simulation_controller, 'monitoring_system'):
            self.simulation_controller.monitoring_system.stop_realtime_monitoring()

        super().closeEvent(event)

    @property
    def mode(self) -> Mode:
        """Возвращает текущий режим работы (обычный или симуляция)."""
        return self.mode_switch.mode

    @mode.setter
    def mode(self, new_mode: Mode):
        """Установка нового режима работы."""
        self.mode_switch.mode = new_mode

    def open_configure_smo(self):
        """Открывает диалог создания новой конфигурации сети Петри."""
        # Проверяем, существует ли уже окно и открыто ли оно
        if self.configure_dialog is None or not self.configure_dialog.isVisible():
            # Создаём новое окно QDialog для конфигурации
            self.configure_dialog = QDialog(self)
            # Загружаем интерфейс из configure_smo.ui в диалог
            uic.loadUi(str((Path(__file__).parent.parent / 'editor' / 'configure_smo.ui').resolve()), self.configure_dialog)
            # Показываем окно
            self.configure_dialog.exec_()
        else:
            # Если окно уже открыто, делаем его активным
            self.configure_dialog.activateWindow()

    def choose_filename_save(self) -> None:
        """Открывает диалог выбора имени файла для сохранения."""
        filename, _ = QFileDialog.getSaveFileName(
            parent=self,
            caption='Выберите файл для сохранения петрограммы в JSON формате',
            directory=self.filename if self.filename is not None else '.json',
            filter='PetriNet in JSON (*.json);;Все файлы (*.*)'
        )
        if filename:
            self.filename = filename
        else:
            self.filename = None  # Если файл не выбран, сбрасываем имя файла

    def new(self) -> None:
        """Создает новый документ, очищая текущую редакцию."""
        self.editor.clear()  # Очищаем редактор
        self.filename = None  # Сбрасываем имя файла

    def open(self) -> None:
        """Открывает существующий документ."""
        filename, _ = QFileDialog.getOpenFileName(
            parent=self,
            caption='Выберите файл с петрограммой в JSON формате',
            directory='.',
            filter='PetriNet in JSON (*.json);;Все файлы (*.*)'
        )

        if filename:
            self.filename = filename

            try:
                with open(self.filename, 'r') as f:
                    self.editor.load_petrinet(f)  # Загружаем петрограмму
            except FileNotFoundError:
                QMessageBox.warning(self, "Ошибка", 'Файл не найден')

    def save_as(self) -> None:
        """Сохраняет документ под новым именем."""
        if self.editor.verified_petrinet(inform_success=False) is not None:
            self.choose_filename_save()  # Выбор имени файла
            if self.filename:
                self.save_petrinet()  # Сохранение петрограммы

    def save(self) -> None:
        """Сохраняет документ с текущим именем файла."""
        if self.editor.verified_petrinet(inform_success=False) is not None:
            if self.filename is None:
                self.choose_filename_save()  # Если имя файла не задано, выбрать его
            if self.filename:
                self.save_petrinet()  # Сохранение петрограммы

    def save_petrinet(self) -> None:
        """Сохраняет петрограмму в выбранный файл."""
        with open(self.filename, 'w') as f:
            self.editor.save_petrinet(f)  # Сохранение в файл

    def simulation_editor_switched(self, is_simulation: bool) -> None:
        """Переключает режим редактора на симуляцию или обратно."""
        self.mode = Mode.Simulation if is_simulation else Mode.Normal

    def sim_buttons_enabled(self, enabled: bool) -> None:
        """Включает или отключает кнопки симуляции."""
        sim_buttons = (
            self.simulation_run_pushButton,
            self.simulation_step_pushButton,
            self.simulation_reset_pushButton
        )
        for sb in sim_buttons:
            sb.setEnabled(enabled)  # Установка состояния кнопок

    def simulation_run(self) -> None:
        """Запускает симуляцию."""
        self.simulation_controller.run()

    def simulation_step(self) -> None:
        """Выполняет один шаг симуляции."""
        self.simulation_controller.auto_run_next_step = False
        self.simulation_controller.step()

    def simulation_reset(self) -> None:
        """Сбрасывает состояние симуляции."""
        self.simulation_controller.reset()