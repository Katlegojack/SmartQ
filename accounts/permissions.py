from rest_framework.permissions import BasePermission

from .models import Profile


def get_user_profile(user):
    """Safely return a user's Smart Q profile, or None when it does not exist."""
    if not user or not user.is_authenticated:
        return None

    try:
        return user.profile
    except Profile.DoesNotExist:
        return None


def get_object_branch(obj):
    """
    Resolve the branch represented by an object used in a permission check.

    Branch objects expose `id` directly. Counter-like objects expose `.branch`.
    Keeping this logic here avoids duplicating branch-scope checks in every API.
    """
    if obj is None:
        return None

    # Branch itself has opening_time/closing_time and no `.branch` relationship.
    if obj.__class__.__name__ == "Branch":
        return obj

    return getattr(obj, "branch", None)


class SmartQRolePermission(BasePermission):
    """Base permission for APIs restricted to one or more Smart Q roles."""

    allowed_roles = set()
    message = "You do not have permission to perform this Smart Q action."

    def has_permission(self, request, view):
        profile = get_user_profile(request.user)
        if profile is None:
            return False

        return profile.role in self.allowed_roles

    def has_object_permission(self, request, view, obj):
        profile = get_user_profile(request.user)
        if profile is None or profile.role not in self.allowed_roles:
            return False

        # SYSTEM_ADMIN is intentionally global.
        if profile.role == Profile.SYSTEM_ADMIN:
            return True

        branch = get_object_branch(obj)
        if branch is None:
            return False

        # Branch staff may operate/read only their assigned branch.
        return profile.branch_id == branch.id


class IsQueueViewer(SmartQRolePermission):
    """Allow staff roles that need to read live branch/counter queue information."""

    allowed_roles = {
        Profile.RECEPTIONIST,
        Profile.COUNTER_STAFF,
        Profile.BRANCH_MANAGER,
        Profile.SYSTEM_ADMIN,
    }
    message = "Only authorised Smart Q staff can view this queue information."


class IsQueueOperator(SmartQRolePermission):
    """Allow roles that may change live counter/queue state."""

    allowed_roles = {
        Profile.COUNTER_STAFF,
        Profile.BRANCH_MANAGER,
        Profile.SYSTEM_ADMIN,
    }
    message = "Only authorised queue operators can change counter queue state."


class IsBranchManager(SmartQRolePermission):
    """Allow branch managers for their own branch and global system administrators."""

    allowed_roles = {
        Profile.BRANCH_MANAGER,
        Profile.SYSTEM_ADMIN,
    }
    message = "Only a branch manager or system administrator can perform this action."


class IsSystemAdmin(SmartQRolePermission):
    """Allow only Smart Q system administrators."""

    allowed_roles = {Profile.SYSTEM_ADMIN}
    message = "Only a Smart Q system administrator can perform this action."
