from PyQt5.QtWidgets import *
from mainwindow import *


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

    def run(self):
        """
        Отображает главное окно и запускает главный цикл обработки событий приложения.
        """
        self.main_window.show()  # Показывает главное окно
        self.qapp.exec()  # Запускает цикл обработки событий