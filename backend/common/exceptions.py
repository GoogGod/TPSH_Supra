class ScheduleConflictError(Exception):
    """Конфликт: сотрудник уже назначен на пересекающуюся смену."""


class InsufficientStaffError(Exception):
    """Недостаточно сотрудников для покрытия потребности."""


class OvertimeLimitError(Exception):
    """Превышен лимит смен/часов за неделю."""


class PatternViolationError(Exception):
    """Нарушение графика (паттерна работы/отдыха)."""


class ForecastError(Exception):
    """Ошибка прогнозного модуля."""