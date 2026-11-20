from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import redirect
from django.contrib import messages


class OrganizerRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.groups.filter(name='Organizer').exists()
                or self.request.user.is_superuser)

    def handle_no_permission(self):
        messages.error(self.request, 'Доступ только для организаторов')
        return redirect('home')


class ExpertRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.groups.filter(name='Expert').exists()
                or self.request.user.is_superuser)

    def handle_no_permission(self):
        messages.error(self.request, 'Доступ только для экспертов')
        return redirect('home')


class ParticipantRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.groups.filter(name='Participant').exists()
                or self.request.user.is_superuser)

    def handle_no_permission(self):
        messages.error(self.request, 'Доступ только для участников')
        return redirect('home')