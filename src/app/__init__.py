from PyQt5 import uic
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import *
from pathlib import Path

# Устанавливаем корневой путь к директории, где находится текущий файл
root_path = Path(__file__).parent


class App:
    """
    Главный класс приложения, инициализирующий и запускающий PyQt приложение.
    """

    def __init__(self, sys_argv):
        """
        Инициализирует экземпляр приложения и главное окно.

        Args:
            sys_argv (list): Список аргументов командной строки, переданный программе.
        """
        self.qapp = QApplication(sys_argv)  # Создание экземпляра QApplication
        self.main_window = MainWindow()  # Создание экземпляра главного окна

    def run(self):
        """
        Отображает главное окно и запускает главный цикл обработки событий приложения.
        """
        self.main_window.show()  # Показывает главное окно
        self.qapp.exec()  # Запускает цикл обработки событий