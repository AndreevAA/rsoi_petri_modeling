import json

def create_petri_net_from_smo(smo_json):
    # Инициализация структуры сети Петри
    petri_net = {
        "names": ["P_queue", "P_service", "P_busy_servers", "P_waiting", "P_buffer", "P_customers", "T_arrive", "T_service", "T_departure"],
        "places": {},
        "transitions": {},
        "arcs": {},
        "graphics": {}
    }

    # Получаем параметры из JSON
    arrival_rate = smo_json['queue_system']['parameters']['arrival_rate']['normal']['lambda']
    service_rate = smo_json['queue_system']['parameters']['service_rate']['normal']['mu']
    num_servers = smo_json['queue_system']['parameters']['num_servers']
    buffer_size = smo_json['queue_system']['parameters']['buffer_size']
    current_customers = smo_json['queue_system']['state']['current_customers']
    waiting_customers = smo_json['queue_system']['state']['waiting_customers']
    busy_servers = smo_json['queue_system']['state']['busy_servers']

    # Создаем места
    petri_net["places"]["P_customers"] = {"init_tokens": current_customers}
    petri_net["places"]["P_waiting"] = {"init_tokens": waiting_customers}
    petri_net["places"]["P_busy_servers"] = {"init_tokens": busy_servers}
    petri_net["places"]["P_free_servers"] = {"init_tokens": num_servers - busy_servers}
    petri_net["places"]["P_buffer"] = {"init_tokens": 0}  # Лимит буфера можно учитывать
    petri_net["places"]["P_service"] = {"init_tokens": 0}

    # Создаем переходы
    petri_net["transitions"]["T_arrive"] = {}  # Прибытие клиента
    petri_net["transitions"]["T_service"] = {}  # Начало обслуживания
    petri_net["transitions"]["T_departure"] = {}  # Завершение обслуживания

    # Создаем арки
    petri_net["arcs"]["A1"] = [0, 7]  # Переход клиентов в обслуживание
    petri_net["arcs"]["A2"] = [3, 8]  # Клиенты выходят из обслуживания
    petri_net["arcs"]["A3"] = [0, 6]  # Клиенты ожидают

    # Графические координаты (пример, можно адаптировать)
    petri_net["graphics"]["0"] = [-100, 100]
    petri_net["graphics"]["1"] = [-50, 150]
    petri_net["graphics"]["2"] = [0, 100]
    petri_net["graphics"]["3"] = [50, 150]
    petri_net["graphics"]["4"] = [100, 100]
    petri_net["graphics"]["5"] = [150, 50]

    return petri_net


# Примеры использования
smo_json_str = '''{
    "queue_system": {
        "type": "M/M/c",
        "parameters": {
            "arrival_rate": {
                "normal": {
                    "lambda": 8
                }
            },
            "service_rate": {
                "normal": {
                    "mu": 12
                }
            },
            "num_servers": 3,
            "buffer_size": 20
        },
        "state": {
            "current_customers": 10,
            "waiting_customers": 4,
            "busy_servers": 3
        }
    }
}'''

smo_json = json.loads(smo_json_str)
petri_net = create_petri_net_from_smo(smo_json)

# Выводим сеть Петри в JSON
print(json.dumps(petri_net, indent=2))