from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTabWidget, QGridLayout, QLabel, QPushButton,
                             QGroupBox, QTableWidget, QTableWidgetItem, QTextEdit, QSpinBox,
                             QCheckBox, QFileDialog, QMessageBox)
from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtGui import QBrush, QColor
import pyqtgraph as pg
import numpy as np
from collections import deque
import datetime
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


class PetriNetAnalyzer:
    """
    Класс для анализа производительности сети Петри
    """

    def __init__(self, monitoring_system):
        self.monitoring = monitoring_system

    def identify_bottlenecks(self):
        """Определить узкие места в системе"""
        # Анализ загрузки переходов
        transitions_util = {name: self.monitoring.get_transition_utilization(name)
                            for name in self.monitoring.transitions_firings.keys()}

        # Места с наибольшей средней заполненностью
        places_util = {name: self.monitoring.get_place_utilization(name)
                       for name in self.monitoring.places_history.keys()}

        # Находим узкие места на основе анализа
        bottlenecks = []

        # Переходы с низкой загрузкой (потенциальные узкие места)
        low_util_threshold = 0.1
        low_util_transitions = [(name, util) for name, util in transitions_util.items()
                                if util < low_util_threshold]

        # Места с высокой заполненностью (скопление токенов, возможно место ожидания)
        high_util_threshold = 0.8
        high_util_places = [(name, util) for name, util in places_util.items()
                            if util > high_util_threshold]

        # Анализируем связанность узких мест
        for place_name, util in high_util_places:
            # Проверяем переходы после этого места
            place = self.monitoring.controller.petrinet.context.named_elements[place_name]
            downstream_transitions = [arc.target for arc in place.outputs]

            for transition in downstream_transitions:
                if transition.name in [name for name, _ in low_util_transitions]:
                    bottlenecks.append({
                        'type': 'transition_bottleneck',
                        'place': place_name,
                        'transition': transition.name,
                        'place_utilization': util,
                        'transition_utilization': transitions_util[transition.name],
                        'description': f"Токены скапливаются в '{place_name}', переход '{transition.name}' работает медленно"
                    })

        # Если нет очевидных узких мест по связям, просто возвращаем места с высокой загрузкой
        if not bottlenecks and high_util_places:
            for place_name, util in high_util_places:
                bottlenecks.append({
                    'type': 'high_place_utilization',
                    'place': place_name,
                    'utilization': util,
                    'description': f"Высокая загрузка места '{place_name}' ({util:.2f})"
                })

        # Также анализируем места с нулевыми токенами - признак недостаточных ресурсов
        empty_places = [(name, 0) for name, history in self.monitoring.places_history.items()
                        if history and all(tokens == 0 for _, tokens in history[1:])]  # Пропускаем начальное состояние

        for place_name, _ in empty_places:
            bottlenecks.append({
                'type': 'resource_starvation',
                'place': place_name,
                'description': f"Место '{place_name}' постоянно пустое - возможная нехватка ресурсов"
            })

        return bottlenecks

    def calculate_performance_metrics(self):
        """Рассчитать ключевые метрики производительности системы"""
        stats = self.monitoring.get_system_stats()
        steps = stats['steps_count']

        if steps == 0:
            return {
                'throughput': 0,
                'processing_time': 0,
                'resource_utilization': 0,
                'efficiency': 0
            }

        # Пропускная способность системы (переходы/время)
        throughput = stats['avg_throughput']

        # Среднее время обработки (реальное время / количество шагов)
        processing_time = stats['real_time'] / steps if steps > 0 else 0

        # Загрузка ресурсов (средняя загрузка всех мест)
        place_utils = [self.monitoring.get_place_utilization(place)
                       for place in self.monitoring.places_history.keys()]
        resource_utilization = sum(place_utils) / len(place_utils) if place_utils else 0

        # Эффективность системы (отношение результата к затраченным ресурсам)
        # Можно оценить как отношение пропускной способности к количеству ресурсов (токенов)
        efficiency = throughput / max(1, stats['avg_tokens']) if stats['avg_tokens'] > 0 else 0

        return {
            'throughput': throughput,
            'processing_time': processing_time,
            'resource_utilization': resource_utilization,
            'efficiency': efficiency
        }


class ReportGenerator:
    """
    Класс для генерации полных отчетов о производительности системы
    """

    def __init__(self, monitoring_system, analyzer):
        self.monitoring = monitoring_system
        self.analyzer = analyzer

    def generate_pdf_report(self, filename=None):
        """Генерирует PDF-отчет о работе системы"""
        if filename is None:
            now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"petri_net_report_{now}.pdf"

        # Создаем PDF с графиками matplotlib
        with PdfPages(filename) as pdf:
            # Титульная страница
            plt.figure(figsize=(11.69, 8.27))  # A4 size
            plt.axis('off')
            plt.text(0.5, 0.8, 'Отчет о моделировании распределенной системы',
                     fontsize=20, ha='center')
            plt.text(0.5, 0.7, f'Дата: {datetime.datetime.now().strftime("%d.%m.%Y %H:%M")}',
                     fontsize=14, ha='center')
            plt.text(0.5, 0.65, f'Всего шагов: {self.monitoring.get_system_stats()["steps_count"]}',
                     fontsize=14, ha='center')
            pdf.savefig()
            plt.close()

            # График пропускной способности
            plt.figure(figsize=(11.69, 8.27))
            plt.plot(self.monitoring.time_points, self.monitoring.system_throughput)
            plt.title('Пропускная способность системы')
            plt.xlabel('Время моделирования')
            plt.ylabel('Переходов в единицу времени')
            plt.grid(True)
            pdf.savefig()
            plt.close()

            # График количества токенов
            plt.figure(figsize=(11.69, 8.27))
            plt.plot(self.monitoring.time_points, self.monitoring.total_tokens)
            plt.title('Количество токенов в системе')
            plt.xlabel('Время моделирования')
            plt.ylabel('Токены')
            plt.grid(True)
            pdf.savefig()
            plt.close()

            # График времени выполнения шагов
            plt.figure(figsize=(11.69, 8.27))
            steps = list(range(len(self.monitoring.execution_times)))
            times_ms = [t * 1000 for t in self.monitoring.execution_times]
            plt.plot(steps, times_ms)
            plt.title('Время выполнения шагов')
            plt.xlabel('Номер шага')
            plt.ylabel('Время (мс)')
            plt.grid(True)
            pdf.savefig()
            plt.close()

            # График токенов в местах
            plt.figure(figsize=(11.69, 8.27))
            for place_name, history in self.monitoring.places_history.items():
                if history:
                    times, tokens = zip(*history)
                    plt.plot(times, tokens, label=place_name)
            plt.title('Токены в местах')
            plt.xlabel('Время моделирования')
            plt.ylabel('Количество токенов')
            plt.legend()
            plt.grid(True)
            pdf.savefig()
            plt.close()

            # Столбчатая диаграмма срабатываний переходов
            plt.figure(figsize=(11.69, 8.27))
            names = list(self.monitoring.transitions_firings.keys())
            firings = list(self.monitoring.transitions_firings.values())
            plt.bar(names, firings)
            plt.title('Количество срабатываний переходов')
            plt.xlabel('Переход')
            plt.ylabel('Количество срабатываний')
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()
            pdf.savefig()
            plt.close()

            # Анализ производительности
            metrics = self.analyzer.calculate_performance_metrics()
            bottlenecks = self.analyzer.identify_bottlenecks()

            plt.figure(figsize=(11.69, 8.27))
            plt.axis('off')
            plt.text(0.5, 0.95, 'Анализ производительности', fontsize=18, ha='center')

            y_pos = 0.85
            plt.text(0.1, y_pos, f"Пропускная способность: {metrics['throughput']:.2f} переходов/с", fontsize=12)
            y_pos -= 0.05
            plt.text(0.1, y_pos, f"Среднее время обработки: {metrics['processing_time'] * 1000:.2f} мс", fontsize=12)
            y_pos -= 0.05
            plt.text(0.1, y_pos, f"Загрузка ресурсов: {metrics['resource_utilization'] * 100:.0f}%", fontsize=12)
            y_pos -= 0.05
            plt.text(0.1, y_pos, f"Эффективность системы: {metrics['efficiency']:.2f}", fontsize=12)

            y_pos -= 0.1
            plt.text(0.1, y_pos, "Обнаруженные узкие места:", fontsize=14)
            y_pos -= 0.05

            if bottlenecks:
                for i, b in enumerate(bottlenecks, 1):
                    plt.text(0.1, y_pos, f"{i}. {b['description']}", fontsize=12)
                    y_pos -= 0.05
            else:
                plt.text(0.1, y_pos, "Узких мест не обнаружено. Система работает эффективно.", fontsize=12)

            pdf.savefig()
            plt.close()

        return filename


class MonitoringWidget(QWidget):
    """
    Виджет для отображения мониторинга и графиков производительности системы
    """

    def __init__(self, monitoring_system, parent=None):
        super().__init__(parent)
        self.monitoring = monitoring_system
        self.analyzer = PetriNetAnalyzer(self.monitoring)
        self.init_ui()

        # Подключаем сигнал обновления данных
        self.monitoring.data_updated.connect(self.update_charts)

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # Создаем вкладки для разных графиков
        self.tab_widget = QTabWidget()

        # 1. Создаем вкладку общей статистики системы
        self.system_tab = QWidget()
        system_layout = QGridLayout(self.system_tab)

        # Графики для вкладки системной статистики
        self.system_throughput_plot = self.create_line_plot("Пропускная способность", "Время", "Переходов/c")
        self.tokens_plot = self.create_line_plot("Общее количество токенов", "Время", "Токены")
        self.exec_time_plot = self.create_line_plot("Время выполнения шага", "Шаг", "мс")

        # Добавляем графики в сетку
        system_layout.addWidget(self.system_throughput_plot, 0, 0)
        system_layout.addWidget(self.tokens_plot, 0, 1)
        system_layout.addWidget(self.exec_time_plot, 1, 0, 1, 2)

        # 2. Создаем вкладку для мест
        self.places_tab = QWidget()
        places_layout = QVBoxLayout(self.places_tab)
        self.places_plot = self.create_line_plot("Токены в местах", "Время", "Токены")
        places_layout.addWidget(self.places_plot)

        # 3. Создаем вкладку для переходов
        self.transitions_tab = QWidget()
        transitions_layout = QVBoxLayout(self.transitions_tab)
        self.transitions_plot = self.create_bar_plot("Количество срабатываний переходов", "Переход", "Срабатывания")
        transitions_layout.addWidget(self.transitions_plot)

        # 4. Создаем вкладку анализа производительности
        self.analysis_tab = QWidget()
        analysis_layout = QVBoxLayout(self.analysis_tab)

        # Блок для отображения ключевых метрик
        metrics_widget = QWidget()
        metrics_layout = QGridLayout(metrics_widget)

        self.lbl_throughput = QLabel("Пропускная способность: 0.00 переходов/с")
        self.lbl_processing_time = QLabel("Среднее время обработки: 0.00 мс")
        self.lbl_resource_util = QLabel("Загрузка ресурсов: 0%")
        self.lbl_efficiency = QLabel("Эффективность системы: 0.00")

        metrics_layout.addWidget(QLabel("<b>Ключевые метрики производительности</b>"), 0, 0, 1, 2)
        metrics_layout.addWidget(self.lbl_throughput, 1, 0)
        metrics_layout.addWidget(self.lbl_processing_time, 1, 1)
        metrics_layout.addWidget(self.lbl_resource_util, 2, 0)
        metrics_layout.addWidget(self.lbl_efficiency, 2, 1)

        # Блок для отображения узких мест
        bottlenecks_widget = QWidget()
        bottlenecks_layout = QVBoxLayout(bottlenecks_widget)
        bottlenecks_layout.addWidget(QLabel("<b>Обнаруженные узкие места</b>"))

        self.bottlenecks_list = QTextEdit()
        self.bottlenecks_list.setReadOnly(True)
        bottlenecks_layout.addWidget(self.bottlenecks_list)

        # Кнопка для выполнения анализа
        self.btn_analyze = QPushButton("Выполнить анализ производительности")
        self.btn_analyze.clicked.connect(self.perform_analysis)

        # Добавляем все элементы на вкладку анализа
        analysis_layout.addWidget(metrics_widget)
        analysis_layout.addWidget(bottlenecks_widget)
        analysis_layout.addWidget(self.btn_analyze)

        # 5. Создаем вкладку настроек мониторинга
        self.settings_tab = QWidget()
        settings_layout = QGridLayout(self.settings_tab)

        # Интервал обновления в реальном времени
        settings_layout.addWidget(QLabel("Интервал обновления (мс):"), 0, 0)
        self.update_interval_spinbox = QSpinBox()
        self.update_interval_spinbox.setRange(100, 5000)
        self.update_interval_spinbox.setSingleStep(100)
        self.update_interval_spinbox.setValue(500)
        self.update_interval_spinbox.valueChanged.connect(self.update_monitoring_settings)
        settings_layout.addWidget(self.update_interval_spinbox, 0, 1)

        # Максимальное количество точек данных для хранения
        settings_layout.addWidget(QLabel("Макс. количество точек данных:"), 1, 0)
        self.max_data_points_spinbox = QSpinBox()
        self.max_data_points_spinbox.setRange(100, 100000)
        self.max_data_points_spinbox.setSingleStep(1000)
        self.max_data_points_spinbox.setValue(10000)
        self.max_data_points_spinbox.valueChanged.connect(self.update_monitoring_settings)
        settings_layout.addWidget(self.max_data_points_spinbox, 1, 1)

        # Размер окна для скользящего среднего
        settings_layout.addWidget(QLabel("Размер окна для среднего:"), 2, 0)
        self.window_size_spinbox = QSpinBox()
        self.window_size_spinbox.setRange(1, 100)
        self.window_size_spinbox.setValue(10)
        self.window_size_spinbox.valueChanged.connect(self.update_monitoring_settings)
        settings_layout.addWidget(self.window_size_spinbox, 2, 1)

        # Включение/выключение мониторинга в реальном времени
        settings_layout.addWidget(QLabel("Мониторинг в реальном времени:"), 3, 0)
        self.realtime_checkbox = QCheckBox()
        self.realtime_checkbox.setChecked(True)
        self.realtime_checkbox.stateChanged.connect(self.toggle_realtime_monitoring)
        settings_layout.addWidget(self.realtime_checkbox, 3, 1)

        # 6. Создаем вкладку диагностики системы
        self.diagnostics_tab = QWidget()
        diagnostics_layout = QVBoxLayout(self.diagnostics_tab)

        # Панель для отображения текущего состояния системы
        current_state_group = QGroupBox("Текущее состояние системы")
        current_state_layout = QVBoxLayout(current_state_group)

        # Таблица для отображения информации о местах
        self.places_table = QTableWidget()
        self.places_table.setColumnCount(3)
        self.places_table.setHorizontalHeaderLabels(["Место", "Токены", "Загрузка"])
        self.places_table.horizontalHeader().setStretchLastSection(True)
        current_state_layout.addWidget(self.places_table)

        # Таблица для отображения информации о переходах
        self.transitions_table = QTableWidget()
        self.transitions_table.setColumnCount(3)
        self.transitions_table.setHorizontalHeaderLabels(["Переход", "Срабатывания", "Загрузка"])
        self.transitions_table.horizontalHeader().setStretchLastSection(True)
        current_state_layout.addWidget(self.transitions_table)

        # Кнопка обновления информации
        self.btn_update_diagnostics = QPushButton("Обновить диагностику")
        self.btn_update_diagnostics.clicked.connect(self.update_diagnostics)
        current_state_layout.addWidget(self.btn_update_diagnostics)

        diagnostics_layout.addWidget(current_state_group)

        # Добавляем вкладки в виджет
        self.tab_widget.addTab(self.system_tab, "Общая статистика")
        self.tab_widget.addTab(self.places_tab, "Места")
        self.tab_widget.addTab(self.transitions_tab, "Переходы")
        self.tab_widget.addTab(self.analysis_tab, "Анализ производительности")
        self.tab_widget.addTab(self.settings_tab, "Настройки мониторинга")
        self.tab_widget.addTab(self.diagnostics_tab, "Диагностика")

        # Панель с текущими статистическими показателями
        self.stats_widget = QWidget()
        stats_layout = QGridLayout(self.stats_widget)

        # Статистические метрики
        self.lbl_step_count = QLabel("Шагов: 0")
        self.lbl_sim_time = QLabel("Время симуляции: 0.00")
        self.lbl_real_time = QLabel("Реальное время: 0.00")
        self.lbl_avg_throughput = QLabel("Средняя пропускная способность: 0.00")
        self.lbl_avg_tokens = QLabel("Среднее число токенов: 0.00")
        self.lbl_avg_exec_time = QLabel("Среднее время шага: 0.00 мс")

        # Кнопки для экспорта данных и создания отчета
        self.btn_export = QPushButton("Экспорт данных")
        self.btn_export.clicked.connect(self.export_data)

        self.btn_export_report = QPushButton("Создать PDF-отчет")
        self.btn_export_report.clicked.connect(self.export_pdf_report)

        # Добавляем метрики в сетку
        stats_layout.addWidget(self.lbl_step_count, 0, 0)
        stats_layout.addWidget(self.lbl_sim_time, 0, 1)
        stats_layout.addWidget(self.lbl_real_time, 0, 2)
        stats_layout.addWidget(self.lbl_avg_throughput, 1, 0)
        stats_layout.addWidget(self.lbl_avg_tokens, 1, 1)
        stats_layout.addWidget(self.lbl_avg_exec_time, 1, 2)
        stats_layout.addWidget(self.btn_export, 2, 0)
        stats_layout.addWidget(self.btn_export_report, 2, 1, 1, 2)

        # Добавляем все на главный слой
        main_layout.addWidget(self.stats_widget)
        main_layout.addWidget(self.tab_widget)

    def create_line_plot(self, title, x_label, y_label):
        """Создать график с линиями"""
        plot = pg.PlotWidget()
        plot.setBackground('w')
        plot.setTitle(title)
        plot.setLabel('bottom', x_label)
        plot.setLabel('left', y_label)
        plot.showGrid(x=True, y=True)
        plot.addLegend()
        return plot

    def create_bar_plot(self, title, x_label, y_label):
        """Создать столбчатый график"""
        plot = pg.PlotWidget()
        plot.setBackground('w')
        plot.setTitle(title)
        plot.setLabel('bottom', x_label)
        plot.setLabel('left', y_label)
        return plot

    @pyqtSlot()
    def update_charts(self):
        """Обновить все графики на основе текущих данных мониторинга"""
        # Обновляем текстовые метрики
        stats = self.monitoring.get_system_stats()
        self.lbl_step_count.setText(f"Шагов: {stats['steps_count']}")
        self.lbl_sim_time.setText(f"Время симуляции: {stats['simulation_time']:.2f}")
        self.lbl_real_time.setText(f"Реальное время: {stats['real_time']:.2f}")
        self.lbl_avg_throughput.setText(f"Средняя пропускная способность: {stats['avg_throughput']:.2f}")
        self.lbl_avg_tokens.setText(f"Среднее число токенов: {stats['avg_tokens']:.2f}")
        self.lbl_avg_exec_time.setText(f"Среднее время шага: {stats['avg_execution_time'] * 1000:.2f} мс")

        # Обновляем график пропускной способности
        self.system_throughput_plot.clear()
        if self.monitoring.time_points and self.monitoring.system_throughput:
            self.system_throughput_plot.plot(
                self.monitoring.time_points,
                self.monitoring.system_throughput,
                pen=pg.mkPen('b', width=2)
            )

        # Обновляем график количества токенов
        self.tokens_plot.clear()
        if self.monitoring.time_points and self.monitoring.total_tokens:
            self.tokens_plot.plot(
                self.monitoring.time_points,
                self.monitoring.total_tokens,
                pen=pg.mkPen('g', width=2)
            )

        # Обновляем график времени выполнения
        self.exec_time_plot.clear()
        if self.monitoring.execution_times:
            steps = list(range(len(self.monitoring.execution_times)))
            # Преобразуем в миллисекунды для наглядности
            times = [t * 1000 for t in self.monitoring.execution_times]
            self.exec_time_plot.plot(
                steps, times,
                pen=pg.mkPen('r', width=2)
            )

        # Обновляем график токенов в местах
        self.places_plot.clear()
        colors = ['b', 'g', 'r', 'c', 'm', 'y', 'k']

        for i, (place_name, history) in enumerate(self.monitoring.places_history.items()):
            if history:
                times, tokens = zip(*history)
                self.places_plot.plot(
                    times, tokens,
                    pen=pg.mkPen(colors[i % len(colors)], width=2),
                    name=place_name
                )

        # Обновляем столбчатый график срабатывания переходов
        self.transitions_plot.clear()
        if self.monitoring.transitions_firings:
            names = list(self.monitoring.transitions_firings.keys())
            firings = list(self.monitoring.transitions_firings.values())

            # Создаем столбчатую диаграмму
            x = np.arange(len(names))
            bar_graph = pg.BarGraphItem(x=x, height=firings, width=0.6, brush='b')
            self.transitions_plot.addItem(bar_graph)

            # Настраиваем оси
            axis = self.transitions_plot.getAxis('bottom')
            axis.setTicks([list(zip(x, names))])

    def export_data(self):
        """Экспортировать данные мониторинга в CSV файл"""
        import csv

        # Получаем путь для сохранения файла
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename, _ = QFileDialog.getSaveFileName(
            self, "Экспорт данных мониторинга",
            f"petri_net_monitoring_{now}.csv",
            "CSV Files (*.csv)"
        )

        if not filename:
            return

        try:
            with open(filename, 'w', newline='') as csvfile:
                # Экспорт основных метрик
                writer = csv.writer(csvfile)
                writer.writerow(["Шаг", "Время симуляции", "Реальное время",
                                 "Пропускная способность", "Всего токенов",
                                 "Время выполнения (мс)"])

                for step in self.monitoring.steps_data:
                    writer.writerow([
                        step['step_num'],
                        step['simulation_time'],
                        step['real_time'],
                        step['throughput'],
                        step['total_tokens'],
                        step['execution_time'] * 1000  # в миллисекундах
                    ])

                # Добавляем пустую строку-разделитель
                writer.writerow([])

                # Экспорт статистики по переходам
                writer.writerow(["Статистика по переходам"])
                writer.writerow(["Переход", "Количество срабатываний", "Коэффициент загрузки"])

                for t_name, firings in self.monitoring.transitions_firings.items():
                    utilization = self.monitoring.get_transition_utilization(t_name)
                    writer.writerow([t_name, firings, utilization])

                # Экспорт статистики по местам
                writer.writerow([])
                writer.writerow(["Статистика по местам"])
                writer.writerow(["Место", "Средние токены", "Максимальные токены"])

                for place_name, history in self.monitoring.places_history.items():
                    if history:
                        _, tokens = zip(*history)
                        avg_tokens = sum(tokens) / len(tokens)
                        max_tokens = max(tokens)
                        writer.writerow([place_name, avg_tokens, max_tokens])

            QMessageBox.information(self, "Экспорт завершен",
                                    f"Данные мониторинга успешно экспортированы в {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка экспорта",
                                     f"Не удалось экспортировать данные: {str(e)}")

    def export_pdf_report(self):
        """Экспортировать полный PDF-отчет с графиками и аналитикой"""
        # Получаем путь для сохранения файла
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename, _ = QFileDialog.getSaveFileName(
            self, "Сохранить отчет",
            f"petri_net_report_{now}.pdf",
            "PDF Files (*.pdf)"
        )

        if not filename:
            return

        try:
            # Создаем генератор отчетов
            report_generator = ReportGenerator(self.monitoring, self.analyzer)
            report_file = report_generator.generate_pdf_report(filename)

            QMessageBox.information(self, "Экспорт завершен",
                                    f"Отчет успешно сохранен в {report_file}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка создания отчета",
                                 f"Не удалось создать отчет: {str(e)}")

    def perform_analysis(self):
        """Выполнить анализ производительности и обновить интерфейс"""
        # Рассчитываем метрики производительности
        metrics = self.analyzer.calculate_performance_metrics()

        # Обновляем метрики на интерфейсе
        self.lbl_throughput.setText(f"Пропускная способность: {metrics['throughput']:.2f} переходов/с")
        self.lbl_processing_time.setText(f"Среднее время обработки: {metrics['processing_time'] * 1000:.2f} мс")
        self.lbl_resource_util.setText(f"Загрузка ресурсов: {metrics['resource_utilization'] * 100:.0f}%")
        self.lbl_efficiency.setText(f"Эффективность системы: {metrics['efficiency']:.2f}")

        # Находим узкие места
        bottlenecks = self.analyzer.identify_bottlenecks()

        # Обновляем список узких мест
        self.bottlenecks_list.clear()
        if bottlenecks:
            bottleneck_text = ""
            for i, b in enumerate(bottlenecks, 1):
                bottleneck_text += f"{i}. {b['description']}\n"
            self.bottlenecks_list.setText(bottleneck_text)
        else:
            self.bottlenecks_list.setText("Узких мест не обнаружено. Система работает эффективно.")

    def update_diagnostics(self):
        """Обновить таблицы диагностики системы"""
        # Обновляем таблицу мест
        self.places_table.setRowCount(0)
        for i, (place_name, history) in enumerate(self.monitoring.places_history.items()):
            if not history:
                continue

            self.places_table.insertRow(i)

            # Имя места
            self.places_table.setItem(i, 0, QTableWidgetItem(place_name))

            # Текущее количество токенов (последнее значение)
            current_tokens = history[-1][1] if history else 0
            self.places_table.setItem(i, 1, QTableWidgetItem(str(current_tokens)))

            # Средняя загрузка места
            utilization = self.monitoring.get_place_utilization(place_name)
            util_item = QTableWidgetItem(f"{utilization:.2f}")

            # Подсветка высокой загрузки красным
            if utilization > 0.8:
                util_item.setForeground(QBrush(QColor(255, 0, 0)))

            self.places_table.setItem(i, 2, util_item)

        # Обновляем таблицу переходов
        self.transitions_table.setRowCount(0)
        for i, (transition_name, firings) in enumerate(self.monitoring.transitions_firings.items()):
            self.transitions_table.insertRow(i)

            # Имя перехода
            self.transitions_table.setItem(i, 0, QTableWidgetItem(transition_name))

            # Количество срабатываний
            self.transitions_table.setItem(i, 1, QTableWidgetItem(str(firings)))

            # Загрузка перехода
            utilization = self.monitoring.get_transition_utilization(transition_name)
            util_item = QTableWidgetItem(f"{utilization:.2f}")

            # Подсветка низкой загрузки (потенциальное узкое место) красным
            if utilization < 0.1 and firings > 0:  # Исключаем неиспользуемые переходы
                util_item.setForeground(QBrush(QColor(255, 0, 0)))

            self.transitions_table.setItem(i, 2, util_item)

        # Подгоняем ширину столбцов
        self.places_table.resizeColumnsToContents()
        self.transitions_table.resizeColumnsToContents()

    def update_monitoring_settings(self):
        """Обновить настройки системы мониторинга"""
        # Обновляем интервал обновления
        if hasattr(self.monitoring, 'realtime_timer') and self.monitoring.realtime_timer.isActive():
            self.monitoring.realtime_timer.setInterval(self.update_interval_spinbox.value())

        # Обновляем максимальное количество точек
        self.monitoring.max_history_size = self.max_data_points_spinbox.value()

        # Обновляем размер окна для скользящего среднего
        window_size = self.window_size_spinbox.value()
        if window_size != self.monitoring.window_size:
            self.monitoring.window_size = window_size
            # Создаем новую очередь с новым размером окна
            old_queue = list(self.monitoring.execution_times_window)
            self.monitoring.execution_times_window = deque(maxlen=window_size)
            # Переносим данные из старой очереди, начиная с конца (самые новые данные)
            for item in old_queue[-window_size:]:
                self.monitoring.execution_times_window.append(item)

    def toggle_realtime_monitoring(self, state):
        """Включить/выключить мониторинг в реальном времени"""
        if state == Qt.Checked:
            self.monitoring.start_realtime_monitoring(self.update_interval_spinbox.value())
        else:
            self.monitoring.stop_realtime_monitoring()