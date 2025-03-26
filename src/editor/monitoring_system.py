from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from collections import deque, defaultdict
import time
import datetime  # Добавляем для отчета в PDF


class MonitoringSystem(QObject):
    """
    Система мониторинга для сбора и анализа статистики о работе сети Петри
    """
    data_updated = pyqtSignal()

    def __init__(self, simulation_controller=None):
        super().__init__()
        self.controller = simulation_controller

        # Настройки системы мониторинга
        self.window_size = 10  # Размер окна для скользящего среднего
        self.max_history_size = 10000  # Максимальное количество сохраняемых точек

        # Данные мониторинга
        self.start_time = None  # Время начала мониторинга
        self.time_points = []  # Временные точки для графиков
        self.system_throughput = []  # Пропускная способность системы
        self.total_tokens = []  # Общее количество токенов
        self.execution_times = []  # Время выполнения каждого шага
        self.execution_times_window = deque(maxlen=self.window_size)  # Скользящее окно для времени выполнения
        self.places_history = defaultdict(list)  # История токенов по местам
        self.transitions_firings = defaultdict(int)  # Количество срабатываний переходов
        self.steps_data = []  # Подробные данные по каждому шагу

        # Таймер для мониторинга в режиме реального времени
        self.realtime_timer = QTimer()
        self.realtime_timer.timeout.connect(self.update_data)

        # Флаг активации мониторинга
        self.is_monitoring_active = False

        # Связываем систему мониторинга с контроллером симуляции
        if simulation_controller:
            self.connect_to_controller(simulation_controller)

    def connect_to_controller(self, controller):
        """Подключить систему мониторинга к контроллеру симуляции"""
        self.controller = controller

        # Для SimulationController не нужно использовать подход с сигналами,
        # так как controller напрямую вызывает методы monitoring_system

    def start_monitoring(self):
        """Запустить мониторинг"""
        self.start_time = time.time()
        self.clear_statistics()
        self.is_monitoring_active = True

    def stop_monitoring(self):
        """Остановить мониторинг"""
        self.is_monitoring_active = False
        self.stop_realtime_monitoring()

    def record_step(self):
        """
        Записать данные о текущем шаге симуляции - этот метод вызывается из SimulationController
        """
        if not self.is_monitoring_active or not self.controller:
            return

        # Вычисляем время выполнения шага
        current_time = time.time()
        step_execution_time = 0.01  # Время по умолчанию

        # Собираем информацию о текущем состоянии сети
        step_data = self.collect_step_data(step_execution_time)

        # Записываем данные
        self.record_step_data(step_data)

        # Сообщаем о обновлении данных
        self.data_updated.emit()

    def collect_step_data(self, execution_time):
        """Собрать данные о текущем шаге симуляции"""
        if not self.controller or not hasattr(self.controller, 'petrinet'):
            return {}

        # Формируем данные о шаге
        step_data = {
            'execution_time': execution_time,
            'simulation_time': self.controller.time,
            'places_tokens': {},
            'fired_transitions': []
        }

        # Получаем информацию о токенах в местах
        try:
            for place in self.controller.petrinet.places:
                step_data['places_tokens'][place.name] = place.tokens
        except (AttributeError, TypeError) as e:
            print(f"Error collecting places data: {str(e)}")

        # Получаем информацию о сработавших переходах
        try:
            step_data['fired_transitions'] = [t.name for t in self.controller.petrinet.fired]
        except (AttributeError, TypeError) as e:
            print(f"Error collecting transitions data: {str(e)}")

        return step_data

    def manual_step_data_collection(self):
        """Ручной сбор данных о шаге"""
        step_data = self.collect_step_data(0.01)
        self.record_step_data(step_data)

    def on_simulation_started(self):
        """Обработчик события начала симуляции"""
        self.start_monitoring()

    def on_simulation_stopped(self):
        """Обработчик события остановки симуляции"""
        self.stop_monitoring()

    def record_step_data(self, step_data):
        """Записать данные о шаге симуляции"""
        # Измеряем время выполнения
        exec_time = step_data.get('execution_time', 0)
        self.execution_times.append(exec_time)
        self.execution_times_window.append(exec_time)

        # Получаем текущее время симуляции
        sim_time = step_data.get('simulation_time', 0)
        real_time = time.time() - self.start_time if self.start_time else 0

        # Получаем информацию о токенах и переходах
        total_tokens = 0
        for place_name, tokens in step_data.get('places_tokens', {}).items():
            self.places_history[place_name].append((sim_time, tokens))
            total_tokens += tokens

            # Ограничиваем размер истории
            if len(self.places_history[place_name]) > self.max_history_size:
                self.places_history[place_name] = self.places_history[place_name][-self.max_history_size:]

        # Записываем срабатывания переходов
        for transition_name in step_data.get('fired_transitions', []):
            self.transitions_firings[transition_name] += 1

        # Рассчитываем пропускную способность
        throughput = len(step_data.get('fired_transitions', [])) / max(exec_time, 0.001)

        # Сохраняем данные для графиков
        self.time_points.append(sim_time)
        self.system_throughput.append(throughput)
        self.total_tokens.append(total_tokens)

        # Ограничиваем размер истории
        if len(self.time_points) > self.max_history_size:
            self.time_points = self.time_points[-self.max_history_size:]
            self.system_throughput = self.system_throughput[-self.max_history_size:]
            self.total_tokens = self.total_tokens[-self.max_history_size:]
            self.execution_times = self.execution_times[-self.max_history_size:]

        # Сохраняем полные данные о шаге
        step_info = {
            'step_num': len(self.steps_data) + 1,
            'simulation_time': sim_time,
            'real_time': real_time,
            'execution_time': exec_time,
            'throughput': throughput,
            'total_tokens': total_tokens,
            'fired_transitions': step_data.get('fired_transitions', [])
        }
        self.steps_data.append(step_info)

        # Ограничиваем количество сохраняемых шагов
        if len(self.steps_data) > self.max_history_size:
            self.steps_data = self.steps_data[-self.max_history_size:]

    def update_data(self):
        """Обновить данные и уведомить интерфейс"""
        if not self.is_monitoring_active or not self.controller:
            return

        # При обновлении данных в режиме реального времени
        self.manual_step_data_collection()

        # Обновляем графики и уведомляем интерфейс
        self.data_updated.emit()

    def get_current_state(self):
        """Получить текущее состояние сети Петри"""
        if not self.controller or not hasattr(self.controller, 'petrinet'):
            return {'places': {}, 'transitions': {}}

        state = {
            'places': {},
            'transitions': {}
        }

        # Получаем информацию о местах
        try:
            for place in self.controller.petrinet.places:
                # Безопасное получение атрибутов
                place_name = place.name if hasattr(place, 'name') else f"Place_{id(place)}"
                tokens = place.tokens if hasattr(place, 'tokens') else 0
                capacity = place.capacity if hasattr(place, 'capacity') else float('inf')

                state['places'][place_name] = {
                    'tokens': tokens,
                    'capacity': capacity
                }
        except (AttributeError, TypeError):
            # Если что-то пошло не так, возвращаем пустой словарь
            pass

        # Получаем информацию о переходах
        try:
            for transition in self.controller.petrinet.transitions:
                # Безопасное получение атрибутов
                transition_name = transition.name if hasattr(transition, 'name') else f"Transition_{id(transition)}"

                # Безопасная проверка, включен ли переход
                try:
                    enabled = transition.is_enabled(self.controller.petrinet)
                except:
                    enabled = False

                state['transitions'][transition_name] = {
                    'enabled': enabled,
                    'just_fired': transition in self.controller.petrinet.fired
                }
        except (AttributeError, TypeError):
            # Если что-то пошло не так, возвращаем пустой словарь
            pass

        return state

    def clear_statistics(self):
        """Очистить все статистические данные"""
        self.time_points = []
        self.system_throughput = []
        self.total_tokens = []
        self.execution_times = []
        self.execution_times_window.clear()
        self.places_history = defaultdict(list)
        self.transitions_firings = defaultdict(int)
        self.steps_data = []

        # Обновляем интерфейс
        self.data_updated.emit()

    def get_system_stats(self):
        """Получить агрегированную статистику о системе"""
        steps_count = len(self.steps_data)

        if steps_count == 0:
            return {
                'steps_count': 0,
                'simulation_time': 0,
                'real_time': 0,
                'avg_throughput': 0,
                'avg_tokens': 0,
                'avg_execution_time': 0
            }

        # Время симуляции и реальное время
        simulation_time = self.time_points[-1] if self.time_points else 0
        real_time = self.steps_data[-1]['real_time'] if self.steps_data else 0

        # Среднее количество токенов и пропускная способность
        avg_tokens = sum(self.total_tokens) / len(self.total_tokens) if self.total_tokens else 0
        total_transitions = sum(self.transitions_firings.values())
        avg_throughput = total_transitions / real_time if real_time > 0 else 0

        # Среднее время выполнения шага
        avg_execution_time = sum(self.execution_times) / len(self.execution_times) if self.execution_times else 0

        return {
            'steps_count': steps_count,
            'simulation_time': simulation_time,
            'real_time': real_time,
            'avg_throughput': avg_throughput,
            'avg_tokens': avg_tokens,
            'avg_execution_time': avg_execution_time
        }

    def get_place_utilization(self, place_name):
        """Получить коэффициент использования места"""
        if place_name not in self.places_history or not self.places_history[place_name]:
            return 0

        # Найдем место в сети Петри, чтобы получить его емкость
        place = None
        try:
            if self.controller and hasattr(self.controller, 'petrinet'):
                for p in self.controller.petrinet.places:
                    if p.name == place_name:
                        place = p
                        break
        except (AttributeError, TypeError):
            pass

        # Если место найдено и у него есть ограниченная емкость, используем ее
        max_capacity = 1  # Значение по умолчанию

        try:
            if place and hasattr(place, 'capacity'):
                max_capacity = place.capacity if place.capacity < float('inf') else 1
        except (AttributeError, TypeError):
            pass

        # Вычисляем среднее количество токенов
        tokens_history = [tokens for _, tokens in self.places_history[place_name]]
        avg_tokens = sum(tokens_history) / len(tokens_history) if tokens_history else 0

        # Вычисляем коэффициент использования
        utilization = avg_tokens / max_capacity if max_capacity > 0 else 0

        return min(utilization, 1.0)  # Не более 100%

    def get_transition_utilization(self, transition_name):
        """Получить коэффициент использования перехода"""
        if not self.transitions_firings or transition_name not in self.transitions_firings:
            return 0

    def get_transitions_stats(self):
        """Получить статистику по всем переходам"""
        stats = {}

        for transition_name, firings in self.transitions_firings.items():
            stats[transition_name] = {
                'firings': firings,
                'utilization': self.get_transition_utilization(transition_name)
            }

        return stats

    def get_places_stats(self):
        """Получить статистику по всем местам"""
        stats = {}

        for place_name in self.places_history.keys():
            if not self.places_history[place_name]:
                continue

            # Вычисляем статистику по токенам
            tokens_history = [tokens for _, tokens in self.places_history[place_name]]

            stats[place_name] = {
                'min_tokens': min(tokens_history) if tokens_history else 0,
                'max_tokens': max(tokens_history) if tokens_history else 0,
                'avg_tokens': sum(tokens_history) / len(tokens_history) if tokens_history else 0,
                'utilization': self.get_place_utilization(place_name),
                'current_tokens': tokens_history[-1] if tokens_history else 0
            }

        return stats

    def export_statistics_to_csv(self, file_path):
        """Экспортировать статистику в CSV-файл"""
        try:
            import csv

            with open(file_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)

                # Запись заголовка
                writer.writerow(['Step', 'Simulation Time', 'Real Time', 'Execution Time',
                                 'Throughput', 'Total Tokens', 'Fired Transitions'])

                # Запись данных по шагам
                for step in self.steps_data:
                    writer.writerow([
                        step['step_num'],
                        step['simulation_time'],
                        step['real_time'],
                        step['execution_time'],
                        step['throughput'],
                        step['total_tokens'],
                        ','.join(step['fired_transitions'])
                    ])

                # Пустая строка для разделения
                writer.writerow([])

                # Запись статистики по местам
                writer.writerow(['Place Statistics'])
                writer.writerow(['Place Name', 'Min Tokens', 'Max Tokens', 'Avg Tokens',
                                 'Utilization', 'Current Tokens'])

                places_stats = self.get_places_stats()
                for place_name, stats in places_stats.items():
                    writer.writerow([
                        place_name,
                        stats['min_tokens'],
                        stats['max_tokens'],
                        stats['avg_tokens'],
                        stats['utilization'],
                        stats['current_tokens']
                    ])

                # Пустая строка для разделения
                writer.writerow([])

                # Запись статистики по переходам
                writer.writerow(['Transition Statistics'])
                writer.writerow(['Transition Name', 'Firings', 'Utilization'])

                transitions_stats = self.get_transitions_stats()
                for transition_name, stats in transitions_stats.items():
                    writer.writerow([
                        transition_name,
                        stats['firings'],
                        stats['utilization']
                    ])

            return True

        except Exception as e:
            print(f"Error exporting statistics to CSV: {str(e)}")
            return False

    def export_report_to_pdf(self, file_path):
        """Экспортировать отчет в PDF"""
        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_pdf import PdfPages
            import numpy as np

            with PdfPages(file_path) as pdf:
                # Титульная страница
                plt.figure(figsize=(8.5, 11))
                plt.axis('off')
                plt.text(0.5, 0.5, 'Отчет о мониторинге сети Петри',
                         fontsize=20, ha='center')
                plt.text(0.5, 0.45, f'Дата: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
                         fontsize=14, ha='center')
                pdf.savefig()
                plt.close()

                # Основные метрики
                plt.figure(figsize=(8.5, 11))
                plt.title('Основные метрики')

                stats = self.get_system_stats()
                metrics = [
                    f"Количество шагов: {stats['steps_count']}",
                    f"Время симуляции: {stats['simulation_time']:.2f}",
                    f"Реальное время: {stats['real_time']:.2f} сек",
                    f"Средняя пропускная способность: {stats['avg_throughput']:.2f} переходов/сек",
                    f"Среднее количество токенов: {stats['avg_tokens']:.2f}",
                    f"Среднее время выполнения шага: {stats['avg_execution_time']:.4f} сек"
                ]

                for i, metric in enumerate(metrics):
                    plt.text(0.1, 0.9 - i * 0.1, metric, fontsize=12)

                plt.axis('off')
                pdf.savefig()
                plt.close()

                # График пропускной способности
                if self.time_points and self.system_throughput:
                    plt.figure(figsize=(8.5, 6))
                    plt.plot(self.time_points, self.system_throughput)
                    plt.title('Пропускная способность системы')
                    plt.xlabel('Время симуляции')
                    plt.ylabel('Переходов/сек')
                    plt.grid(True)
                    pdf.savefig()
                    plt.close()

                # График общего количества токенов
                if self.time_points and self.total_tokens:
                    plt.figure(figsize=(8.5, 6))
                    plt.plot(self.time_points, self.total_tokens)
                    plt.title('Общее количество токенов в системе')
                    plt.xlabel('Время симуляции')
                    plt.ylabel('Количество токенов')
                    plt.grid(True)
                    pdf.savefig()
                    plt.close()

                # График токенов по местам
                places_to_plot = list(self.places_history.keys())
                if places_to_plot:
                    # Разделим на несколько графиков, если мест много
                    chunk_size = 5
                    for i in range(0, len(places_to_plot), chunk_size):
                        places_chunk = places_to_plot[i:i + chunk_size]
                        plt.figure(figsize=(8.5, 6))

                        for place_name in places_chunk:
                            if not self.places_history[place_name]:
                                continue
                            times, tokens = zip(*self.places_history[place_name])
                            plt.plot(times, tokens, label=place_name)

                        plt.title(f'Количество токенов по местам (часть {i // chunk_size + 1})')
                        plt.xlabel('Время симуляции')
                        plt.ylabel('Количество токенов')
                        plt.legend()
                        plt.grid(True)
                        pdf.savefig()
                        plt.close()

                # Статистика по переходам
                transitions_stats = self.get_transitions_stats()
                if transitions_stats:
                    plt.figure(figsize=(8.5, 6))
                    names = list(transitions_stats.keys())
                    firings = [stats['firings'] for stats in transitions_stats.values()]

                    y_pos = np.arange(len(names))
                    plt.barh(y_pos, firings)
                    plt.yticks(y_pos, names)
                    plt.title('Количество срабатываний переходов')
                    plt.xlabel('Количество срабатываний')
                    plt.tight_layout()
                    pdf.savefig()
                    plt.close()

                    # Коэффициент использования переходов
                    plt.figure(figsize=(8.5, 6))
                    utilization = [stats['utilization'] for stats in transitions_stats.values()]

                    plt.barh(y_pos, utilization)
                    plt.yticks(y_pos, names)
                    plt.title('Коэффициент использования переходов')
                    plt.xlabel('Коэффициент использования')
                    plt.tight_layout()
                    pdf.savefig()
                    plt.close()

                # Статистика по местам
                places_stats = self.get_places_stats()
                if places_stats:
                    plt.figure(figsize=(8.5, 6))
                    names = list(places_stats.keys())
                    avg_tokens = [stats['avg_tokens'] for stats in places_stats.values()]

                    y_pos = np.arange(len(names))
                    plt.barh(y_pos, avg_tokens)
                    plt.yticks(y_pos, names)
                    plt.title('Среднее количество токенов по местам')
                    plt.xlabel('Среднее количество токенов')
                    plt.tight_layout()
                    pdf.savefig()
                    plt.close()

                    # Коэффициент использования мест
                    plt.figure(figsize=(8.5, 6))
                    utilization = [stats['utilization'] for stats in places_stats.values()]

                    plt.barh(y_pos, utilization)
                    plt.yticks(y_pos, names)
                    plt.title('Коэффициент использования мест')
                    plt.xlabel('Коэффициент использования')
                    plt.tight_layout()
                    pdf.savefig()
                    plt.close()

                # Определение узких мест
                analyzer = PetriNetAnalyzer(self)
                bottlenecks = analyzer.identify_bottlenecks()

                if bottlenecks:
                    plt.figure(figsize=(8.5, 11))
                    plt.title('Выявленные узкие места')

                    for i, bottleneck in enumerate(bottlenecks):
                        plt.text(0.1, 0.9 - i * 0.1, bottleneck['description'], fontsize=10)

                    plt.axis('off')
                    pdf.savefig()
                    plt.close()

            return True

        except Exception as e:
            print(f"Error exporting report to PDF: {str(e)}")
            return False

    def start_realtime_monitoring(self, interval=500):
        """Запустить мониторинг в реальном времени"""
        if not self.realtime_timer.isActive():
            self.realtime_timer.start(interval)

    def stop_realtime_monitoring(self):
        """Остановить мониторинг в реальном времени"""
        if self.realtime_timer.isActive():
            self.realtime_timer.stop()