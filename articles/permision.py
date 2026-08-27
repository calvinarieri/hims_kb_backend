from rest_framework import permissions

def has_role_perm(user, perm_code):
    """
    Helper function to check if a user is superuser or has a specific role permission.
    Staff members without a role assigned (user.role is None) are granted default staff permissions.
    """
    if not (user and user.is_authenticated):
        return False
    if user.is_superuser:
        return True
    if not user.is_staff:
        return False
    if user.role is None:
        return True
    if not user.role.permissions:
        return False
    return "*" in user.role.permissions or perm_code in user.role.permissions


class IsStaffOrAdminUser(permissions.BasePermission):
    """
    Allows read/write access only to staff members and superusers (admins).
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class CanReadArticle(permissions.BasePermission):
    """
    Controls read access based on article visibility and status:
    - Staff/Admins: Can read PUBLIC and PRIVATE articles if they have read permissions.
    - Unauthenticated / Non-staff: Can ONLY read PUBLIC + PUBLISHED articles.
    """
    def has_permission(self, request, view):
        is_staff_or_admin = request.user and request.user.is_authenticated and request.user.is_staff
        if is_staff_or_admin:
            return has_role_perm(request.user, 'articles:read')
        return True

    def has_object_permission(self, request, view, obj):
        is_staff_or_admin = request.user and request.user.is_authenticated and request.user.is_staff
        
        if is_staff_or_admin:
            return has_role_perm(request.user, 'articles:read')
            
        return obj.visibility == 'PUBLIC' and obj.status == 'PUBLISHED'


class IsAuthorOrAdminForWrite(permissions.BasePermission):
    """
    Super Admin (superuser) has full access to edit/delete any article.
    Staff members can create articles if they have 'articles:create', and can update/delete ONLY articles they authored
    with 'articles:update' and 'articles:delete' role permissions respectively.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        if not (request.user and request.user.is_authenticated and request.user.is_staff):
            return False
        if request.user.is_superuser:
            return True
        
        if request.method == 'POST':
            return has_role_perm(request.user, 'articles:create')
        elif request.method in ['PUT', 'PATCH']:
            return has_role_perm(request.user, 'articles:update')
        elif request.method == 'DELETE':
            return has_role_perm(request.user, 'articles:delete')
        return False

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
            
        if request.user.is_superuser:
            return True

        if not request.user.is_staff:
            return False
            
        # Check role permission for method
        if request.method in ['PUT', 'PATCH'] and not has_role_perm(request.user, 'articles:update'):
            return False
        if request.method == 'DELETE' and not has_role_perm(request.user, 'articles:delete'):
            return False
            
        # Staff members can update/delete ONLY articles they authored
        return obj.versions.filter(author=request.user).exists()


class CanApproveArticle(permissions.BasePermission):
    """
    Super admins or staff members with 'articles:approve' role permission can approve articles for publishing.
    """
    def has_permission(self, request, view):
        return has_role_perm(request.user, 'articles:approve')