from rest_framework.permissions import BasePermission

EMPLOYEE_ROLES = ("employee_noob", "employee_pro")
MANAGER_ROLES = ("manager", "admin")
ALL_ROLES = EMPLOYEE_ROLES + MANAGER_ROLES


class IsEmployee(BasePermission):
    """Любой авторизованный пользователь."""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated


class IsManager(BasePermission):
    """Менеджер или Администратор."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in MANAGER_ROLES


class IsAdmin(BasePermission):
    """Только Администратор."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role == "admin"


class IsOwnerOrManager(BasePermission):
    def has_object_permission(self, request, view, obj):
        user = request.user
        owner = getattr(obj, "user", None) or getattr(obj, "employee", None)
        if user == owner:
            return True
        return user.role in MANAGER_ROLES