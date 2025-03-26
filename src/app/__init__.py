from PyQt5.QtWidgets import *
from mainwindow import *
from PyQt5.QtCore import QObject


class App:
    """
    Главный класс приложения, инициализирующий и запускающий PyQt приложение.
    """

    def __init__(self, sys_argv, root_path):
        """
        Инициализирует экземпляр приложения и главное окно.

        Args:
            sys_argv (list): Список аргументов командной строки, переданный программе.
            root_path (src): Корневой путь к директории.

        """
        self.root_path = root_path
        self.qapp = QApplication(sys_argv)  # Создание экземпляра QApplication
        self.main_window = MainWindow(root_path)  # Создание экземпляра главного окна

    # app/__init__.py
    def run(self):
        """
        Отображает главное окно и запускает главный цикл обработки событий приложения.
        """
        # Добавляем метод обновления в SimulationController без использования сигналов
        original_step = self.main_window.simulation_controller.step

        def wrapped_step(*args, **kwargs):
            result = original_step(*args, **kwargs)
            # После выполнения шага обновляем мониторинг
            if hasattr(self.main_window, 'monitoring_widget'):
                self.main_window.monitoring_widget.update_charts()
            return result

        # Заменяем оригинальный метод step
        self.main_window.simulation_controller.step = wrapped_step

        self.main_window.show()
        self.qapp.exec()