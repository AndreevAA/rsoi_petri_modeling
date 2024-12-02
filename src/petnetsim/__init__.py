from enum import IntEnum
import numpy as np
from .elements import *


class ConflictGroupType(IntEnum):
    """Типы конфликтных групп в модели конечных автоматов."""
    Normal = 0
    Priority = 1
    Stochastic = 2
    Timed = 3


class PetriNet:
    """Класс для представления сеть Петри.

    Атрибуты
    ---------
    places : tuple
        Кортеж объектов мест сети Петри.
    transitions : tuple
        Кортеж объектов переходов сети Петри.
    arcs : tuple
        Кортеж объектов дуг сети Петри.
    context : dict
        Контекст выполнения модели.

    Методы
    -------
    reset()
        Сбрасывает состояние модели.
    step(record_fired=True)
        Выполняет один шаг симуляции.
    print_places()
        Выводит информацию о местах.
    print_all()
        Выводит полную информацию о сети.
    validate()
        Проверяет корректность модели сети Петри.
    """

    def __init__(self, places, transitions, arcs, context=default_context()):
        """Инициализирует сеть Петри.

        Параметры
        ----------
        places : list
            Список мест (объектов Place) или строковых имен мест.
        transitions : list
            Список переходов (объектов Transition) или строковых имен переходов.
        arcs : list
            Список дуг (объектов Arc или Inhibitor).
        context : dict, необязательно
            Контекст выполнения модели, по умолчанию используется стандартный контекст.

        Исключения
        ----------
        RuntimeError
            Если имена мест, переходов или дуг повторяются.
        """
        self._names_lookup = {}

        # Создание объектов мест из строк названий или инициализация существующих объектов
        places = [Place(p, context=context) if isinstance(p, str) else p for p in places]

        # Проверка на уникальность имен мест
        for p in places:
            if p.name in self._names_lookup:
                raise RuntimeError('name reused: ' + p.name)
            self._names_lookup[p.name] = p

        # Создание объектов переходов из строк названий или инициализация существующих объектов
        transitions = [Transition(t, context=context) if isinstance(t, str) else t
                       for t in transitions]

        # Проверка на уникальность имен переходов
        for t in transitions:
            if t.name in self._names_lookup:
                raise RuntimeError('name reused: ' + t.name)
            self._names_lookup[t.name] = t

        def get_i(obj, i, default=1):
            """Получает элемент из списка по индексу или возвращает значение по умолчанию."""
            try:
                v = obj[i]
            except IndexError:
                v = default
            return v

        # Создание дуг, проверка их имен и подключение к местам и переходам
        arcs = [Arc(a[0], a[1], get_i(a, 2), get_i(a, 3, None), context=context)
                if isinstance(a, (tuple, list)) else a
                for a in arcs]

        for arc in arcs:
            if arc.name in self._names_lookup:
                raise RuntimeError('name reused: ' + arc.name)
            self._names_lookup[arc.name] = arc
            arc.connect(self._names_lookup)

        # Замораживание переходов для предотвращения изменений после инициализации
        for t in transitions:
            t.freeze()

        # Сохранение объектов мест, переходов и дуг
        self.places = tuple(places)
        self.transitions = tuple(transitions)
        self.arcs = tuple(arcs)

        # Создание конфликтных групп для управления переходами
        self._make_conflict_groups()

        # Инициализация массивов для отслеживания состояние переходов
        self.enabled = np.zeros(len(transitions), dtype=np.bool_)
        self.enabled_tmp = np.zeros(len(transitions), dtype=np.bool_)
        self._ended = False
        self.step_num = 0
        self.time = 0.0
        self.fired = []  # Переходы, которые были активированы
        self.fired_phase2 = []  # Переходы, активируемые во второй фазе

    def clone(self, prefix: str, places, transitions, arcs, context=default_context()):
        """Создает клон сети Петри с новыми именами.

        Параметры
        ----------
        prefix : str
            Префикс для новых имен мест, переходов и дуг.
        places : list
            Список для добавления клонированных мест.
        transitions : list
            Список для добавления клонированных переходов.
        arcs : list
            Список для добавления клонированных дуг.
        context : dict, необязательно
            Контекст выполнения модели, по умолчанию используется стандартный контекст.

        Исключения
        ----------
        TypeError
            Если тип дуги не поддерживается.
        """
        for p in self.places:
            places.append(p.clone(prefix))
        for t in self.transitions:
            transitions.append(t.clone(prefix))
        for a in self.arcs:
            if isinstance(a, Arc):
                arcs.append((prefix + a.source.name, prefix + a.target.name, a.n_tokens, prefix + a.name))
            elif isinstance(a, Inhibitor):
                arcs.append(Inhibitor(prefix + a.source.name, prefix + a.target.name, a.n_tokens, prefix + a.name))
            else:
                raise TypeError(f'cannot handle type: {type(a)}')

    @property
    def ended(self):
        """Возвращает состояние завершения симуляции."""
        return self._ended

    def reset(self):
        """Сбрасывает состояние модели."""
        self._ended = False
        self.step_num = 0
        self.time = 0.0
        self.fired.clear()
        self.conflict_groups_waiting.fill(0)
        for t in self.transitions:
            t.reset()
        for p in self.places:
            p.reset()

    def step(self, record_fired=True):
        """Выполняет один шаг симуляции.

        Параметры
        ----------
        record_fired : bool, необязательно
            Записывать ли активированные переходы, по умолчанию True.
        """
        if record_fired:
            self.fired.clear()
            self.fired_phase2.clear()

        # Проверка на активированные переходы
        for ti, t in enumerate(self.transitions):
            self.enabled[ti] = t.enabled()

        CGT = ConflictGroupType
        num_fired = 0
        enabled_any = self.enabled.any()

        if enabled_any:
            np.bitwise_and(self.enabled, self.conflict_groups_mask, out=self.enabled_conflict_groups)

            for cgi, ecg in enumerate(self.enabled_conflict_groups):
                if ecg.any():
                    cg_type = self.conflict_groups_types[cgi]
                    t_idxs = np.argwhere(ecg).flatten()  # абсолютные индексы активированных переходов в группе
                    t_fire_idx = None

                    # Логика выбора перехода для активации в зависимости от типа конфликтной группы
                    if cg_type == CGT.Normal:
                        t_fire_idx = np.random.choice(t_idxs)
                    elif cg_type == CGT.Priority:
                        priorities = self.conflict_group_data[cgi]
                        ep = priorities[t_idxs]
                        ep_idxs = np.argwhere(ep == ep.max()).flatten()
                        ep_idx = np.random.choice(ep_idxs)
                        t_fire_idx = t_idxs[ep_idx]
                    elif cg_type == CGT.Stochastic:
                        probabilities = self.conflict_group_data[cgi][t_idxs]
                        # "нормализует" сумму вероятностей до 1
                        probabilities_norm = probabilities * (1 / np.sum(probabilities))
                        t_fire_idx = np.random.choice(t_idxs, p=probabilities_norm)
                    elif cg_type == CGT.Timed:
                        if self.conflict_groups_waiting[cgi] <= 0:
                            normal_enabled = self.enabled_tmp
                            np.bitwise_and(ecg, self.conflict_group_data[cgi][1], out=normal_enabled)
                            if any(normal_enabled):  # использование обычного перехода
                                normal_t_idxs = np.argwhere(normal_enabled).flatten()
                                t_fire_idx = np.random.choice(normal_t_idxs)
                            else:  # затем должен быть тайминг
                                timed_enabled = self.enabled_tmp
                                np.bitwise_and(ecg, self.conflict_group_data[cgi][0], out=timed_enabled)
                                timed_t_idxs = np.argwhere(timed_enabled).flatten()
                                timed_t_idx = np.random.choice(timed_t_idxs)
                                t_fire_idx = timed_t_idx
                                timed_t: TransitionTimed = self.transitions[timed_t_idx]
                                self.conflict_groups_waiting[cgi] = timed_t.choose_time()

                    if t_fire_idx is not None:
                        t = self.transitions[t_fire_idx]
                        if t.output_possible():
                            t.fire()
                            num_fired += 1
                            if record_fired:
                                self.fired.append(t)
                        else:
                            print(f'warning: transition "{t.name}" was enabled, but output not possible',
                                  file=sys.stderr)

        num_waiting = np.sum(self.conflict_groups_waiting > 0)

        if num_waiting > 0 and num_fired == 0:
            # ничего не активировалось -> увеличиваем время и активируем ожидающие таймированные переходы
            min_time = np.min(self.conflict_groups_waiting[self.conflict_groups_waiting > 0])
            self.time += min_time

            for cgi in np.argwhere(self.conflict_groups_waiting == min_time).flatten():
                for ti in np.where(self.conflict_group_data[cgi][0])[0]:
                    t: TransitionTimed = self.transitions[ti]
                    if t.is_waiting:
                        if t.output_possible():
                            t.fire_phase2()
                            self.fired_phase2.append(t)
                            break
                        else:
                            msg = f'timed transition "{t.name}" was fired, but output not possible for phase 2'
                            raise RuntimeError(msg)

                self.conflict_groups_waiting[cgi] = 0

            np.subtract(self.conflict_groups_waiting, min_time, out=self.conflict_groups_waiting)
            np.clip(self.conflict_groups_waiting, 0, float('inf'), out=self.conflict_groups_waiting)

        if not enabled_any and num_waiting == 0:
            self._ended = True
        self.step_num += 1

    def print_places(self):
        """Выводит информацию о местах и количестве токенов в них."""
        for p in self.places:
            print(p.name, p.tokens, sep=': ')

    def print_all(self):
        """Выводит полную информацию о местах, переходах и дугах сети Петри."""
        print('places:')
        for p in self.places:
            print('  ', p.name, p.init_tokens)
        print('transitions:')
        for t in self.transitions:
            print('  ', t.name, t.__class__.__name__)
        print('arcs:')
        for a in self.arcs:
            print('  ' if type(a) == Arc else ' I', a.name, a.target.name, '--' + str(a.n_tokens) + '->', a.source.name)

    def validate(self):
        """Проверяет корректность всей сети Петри.

        Заметка
        -------
        В настоящее время реализация проверки отсутствует.
        """
        print('TODO: PetriNet.validate')
        pass

    @property
    def conflict_groups_str(self):
        """Представляет строку, в которой перечислены конфликты между группами переходов."""
        return ', '.join('{' + ', '.join(sorted(t.name for t in s)) + '}' for s in self.conflict_groups_sets)

    def _make_conflict_groups(self):
        """Создает конфликтные группы на основе переходов сети.

        Эта функция анализирует переходы и определяет, какие из них конфликтуют друг с другом,
        создавая для них соответствующие группы.
        """
        conflict_groups_sets = [{self.transitions[0]}] if len(self.transitions) else []
        for t in self.transitions[1:]:
            add_to_cg = False
            for cg in conflict_groups_sets:
                for cg_t in cg:
                    # Игнорируем ингибиторы
                    t_in = set(arc.source for arc in t.inputs if isinstance(arc, Arc))
                    cg_t_in = set(arc.source for arc in cg_t.inputs if isinstance(arc, Arc))

                    add_to_cg = add_to_cg or not t_in.isdisjoint(cg_t_in)
                    if add_to_cg:
                        break
                if add_to_cg:
                    cg.add(t)
                    break

            if not add_to_cg:
                conflict_groups_sets.append({t})

        conflict_groups_types = [None for _ in conflict_groups_sets]

        def t_cg_type(transition):
            """Определяет тип конфликтной группы для перехода."""
            if isinstance(transition, TransitionPriority):
                return ConflictGroupType.Priority
            elif isinstance(transition, TransitionStochastic):
                return ConflictGroupType.Stochastic
            elif isinstance(transition, TransitionTimed):
                return ConflictGroupType.Timed
            return ConflictGroupType.Normal

        CGT = ConflictGroupType
        conflict_group_data = [None for _ in conflict_groups_sets]
        for cg_i, cg in enumerate(conflict_groups_sets):
            # определение типа конфликтной группы по предпочтению переходов
            t_types = [t_cg_type(t) for t in cg]
            if all(tt == CGT.Normal for tt in t_types):
                cg_type = CGT.Normal
            elif all(tt == CGT.Normal or tt == CGT.Priority for tt in t_types):
                cg_type = CGT.Priority
                conflict_group_data[cg_i] = np.zeros(len(self.transitions), dtype=np.uint)
            elif all(tt == CGT.Normal or tt == CGT.Timed for tt in t_types):
                cg_type = CGT.Timed
                conflict_group_data[cg_i] = np.zeros((2, len(self.transitions)), dtype=np.bool_)
            elif all(tt == CGT.Stochastic for tt in t_types):
                group_members_names = ', '.join([t.name for t in cg])
                cg_type = CGT.Stochastic
                one_t_in_cg = next(iter(cg))
                ot_sources = set(i.source for i in one_t_in_cg.inputs)
                if not all(set(i.source for i in t.inputs) == ot_sources for t in cg):
                    raise RuntimeError(
                        'all members of stochastic group must share the same inputs: ' + group_members_names)

                conflict_group_data[cg_i] = np.zeros(len(self.transitions))
            else:
                raise RuntimeError('Unsupported combination of transitions: ' + ', '.join([str(tt) for tt in t_types]) + \
                                   '\n' + '; '.join(c.__class__.__name__ + ': ' + c.name for c in cg))

            conflict_groups_types[cg_i] = cg_type

        self.conflict_groups_waiting = np.zeros(len(conflict_groups_sets))
        self.conflict_groups_sets = tuple(tuple(cg) for cg in conflict_groups_sets)
        self.conflict_groups_types = tuple(conflict_groups_types)
        self.conflict_groups_mask = np.zeros((len(conflict_groups_sets), len(self.transitions)), dtype=np.bool_)
        self.enabled_conflict_groups = np.zeros((len(conflict_groups_sets), len(self.transitions)), dtype=np.bool_)
        for cgi, (cg, cgt) in enumerate(zip(conflict_groups_sets, conflict_groups_types)):
            for ti, t in enumerate(self.transitions):
                t_in_cg = t in cg
                self.conflict_groups_mask[cgi, ti] = t_in_cg

                if t_in_cg:
                    if cgt == CGT.Priority:
                        conflict_group_data[cgi][ti] = t.priority if hasattr(t, 'priority') else 0
                    elif cgt == CGT.Timed:
                        conflict_group_data[cgi][0, ti] = isinstance(t, TransitionTimed)
                        conflict_group_data[cgi][1, ti] = not isinstance(t, TransitionTimed)
                    elif cgt == CGT.Stochastic:
                        conflict_group_data[cgi][ti] = t.probability

        self.conflict_group_data = tuple(conflict_group_data)