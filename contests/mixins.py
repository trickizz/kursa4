from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect
from django.contrib import messages

from .roles import (has_role, ROLE_PARTICIPANT, ROLE_MENTOR, ROLE_EXPERT,
                    ROLE_ORGANIZER, ROLE_ADMIN)


class RoleRequiredMixin(UserPassesTestMixin):
    """Базовый миксин: пускает пользователей с одной из required_roles.
    Администратор и суперпользователь проходят любую проверку."""
    required_roles = ()
    permission_message = 'У вас нет прав для просмотра этой страницы.'

    def test_func(self):
        return has_role(self.request.user, *self.required_roles)

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect_to_login(self.request.get_full_path())
        messages.error(self.request, self.permission_message)
        return redirect('home')


class OrganizerRequiredMixin(RoleRequiredMixin):
    required_roles = (ROLE_ORGANIZER,)
    permission_message = 'Доступ только для организаторов и администраторов.'


class ExpertRequiredMixin(RoleRequiredMixin):
    required_roles = (ROLE_EXPERT,)
    permission_message = 'Доступ только для экспертов и администраторов.'


class ParticipantRequiredMixin(RoleRequiredMixin):
    required_roles = (ROLE_PARTICIPANT,)
    permission_message = 'Доступ только для участников и администраторов.'


class MentorRequiredMixin(RoleRequiredMixin):
    required_roles = (ROLE_MENTOR,)
    permission_message = 'Доступ только для наставников и администраторов.'


class AdminRequiredMixin(RoleRequiredMixin):
    required_roles = (ROLE_ADMIN,)
    permission_message = 'Доступ только для администраторов.'
