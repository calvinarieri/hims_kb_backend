from rest_framework import permissions

class HasRolePermission(permissions.BasePermission):
    """
    Permission check based on user role permissions stored in JSONField.
    Superusers automatically pass.
    """
    def __init__(self, required_permission=None):
        self.required_permission = required_permission

    def __call__(self):
        return self

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        
        # Superuser always has full access
        if request.user.is_superuser:
            return True

        if not request.user.is_staff:
            return False

        perm = self.required_permission or getattr(view, 'required_permission', None)
        if not perm:
            return True

        if not request.user.role or not request.user.role.permissions:
            return False

        role_perms = request.user.role.permissions
        if "*" in role_perms or perm in role_perms:
            return True

        return False

