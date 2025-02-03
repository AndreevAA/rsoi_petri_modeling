import json

from numpy.ma.core import arcsinh


class SMO:


    def __init__(self, names, places, transitions, arcs, graphics):
        self.__set_base_folder()

        self.names = names
        self.places = places
        self.transitions = transitions
        self.arcs = arcs
        self.graphics = graphics

    def __get_config(self):
        self.config = {
            "names": self.names,
            "places": self.places,
            "transitions": self.transitions,
            "arcs": self.arcs,
            "graphics": self.graphics
        }

    def __set_base_folder(self):
        self.folder = "../data"



    def create_smo_config_by_terminal(self):
            print("Введите данные для вашей Системы массового обслуживания (СМО).")

            # Список мест (Places) и количество токенов
            num_places = int(input("Введите количество мест в СМО: "))
            places = []
            for i in range(num_places):
                tokens = int(input(f"Введите количество токенов для места P_{i + 1} (по умолчанию 0): ") or 0)
                places[i] = {"init_tokens": tokens} if tokens > 0 else {}

            # Список переходов (Transitions)
            num_transitions = int(input("Введите количество переходов в СМО: "))
            transitions = {}
            for i in range(num_transitions):
                transitions[num_places + i] = {}

            # Арки (Arcs) между местами и переходами
            print("\nОпределите связи (арки) между местами и переходами.")
            arcs = {}
            arc_counter = num_places + num_transitions
            while True:
                arc_from = input("Введите исходящий узел (P_x или T_x, где x - номер, или 'stop' для завершения): ")
                if arc_from.lower() == "stop":
                    break
                arc_to = input("Введите входящий узел (P_x или T_x, где x - номер): ")

                # Определение типа узлов
                if arc_from.startswith("P"):
                    arc_from = int(arc_from[2:]) - 1
                else:
                    arc_from = num_places + int(arc_from[2:]) - 1

                if arc_to.startswith("P"):
                    arc_to = int(arc_to[2:]) - 1
                else:
                    arc_to = num_places + int(arc_to[2:]) - 1

                # Сохранение арки
                arcs[arc_counter] = [arc_from, arc_to]
                arc_counter += 1

            # Разметка узлов (graphics)
            print("\nОпределите координаты для графического отображения узлов.")
            graphics = {}
            for i in range(num_places):
                x = float(input(f"Введите X-координату для места P_{i + 1}: "))
                y = float(input(f"Введите Y-координату для места P_{i + 1}: "))
                graphics[i] = [x, y]

            for i in range(num_transitions):
                x = float(input(f"Введите X-координату для перехода T_{i + 1}: "))
                y = float(input(f"Введите Y-координату для перехода T_{i + 1}: "))
                graphics[num_places + i] = [x, y]

            # Привязка арок для графического интерфейса
            for arc_id, (start, end) in arcs.items():
                graphics[arc_id] = [start, end]

            # Имена узлов
            names = [f"P_{i + 1}" for i in range(num_places)] + [f"T_{i + 1}" for i in range(num_transitions)] + [
                f"Arc_{i + 1}" for i in range(len(arcs))]

            # Создание конфигурации
            config = {
                "names": names,
                "places": places,
                "transitions": transitions,
                "arcs": arcs,
                "graphics": graphics
            }

            # Сохранение в файл
            save_path = input("Введите имя файла для сохранения конфигурации (например, 'smo_config.json'): ")
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)

            print(f"\nКонфигурация сохранена в файл {save_path}")
            return config

        # Основной запуск программы
        if __name__ == "__main__":
            create_smo_config()