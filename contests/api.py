"""REST API (DRF): конкурсы, проекты, оценки, голосование, профиль. Docs: /api/docs/."""
from django.db.models import Count
from rest_framework import viewsets, permissions, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Contest, Project, Evaluation, ProjectVote
from .roles import primary_role, ROLE_INFO, is_participant


class ContestSerializer(serializers.ModelSerializer):
    organizer = serializers.StringRelatedField()
    project_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Contest
        fields = ['id', 'name', 'description', 'start_date', 'end_date',
                  'is_active', 'results_finalized', 'organizer', 'project_count']


class ProjectSerializer(serializers.ModelSerializer):
    participant = serializers.StringRelatedField(read_only=True)
    contest_name = serializers.CharField(source='contest.name', read_only=True)
    score_percent = serializers.FloatField(read_only=True)

    class Meta:
        model = Project
        fields = ['id', 'title', 'summary', 'contest', 'contest_name', 'participant',
                  'status', 'votes', 'score_percent', 'created_at']
        read_only_fields = ['participant', 'status', 'votes', 'created_at']


class EvaluationSerializer(serializers.ModelSerializer):
    project_title = serializers.CharField(source='project.title', read_only=True)
    expert_name = serializers.CharField(source='expert.username', read_only=True)
    criterion_name = serializers.CharField(source='criterion.name', read_only=True)

    class Meta:
        model = Evaluation
        fields = ['id', 'project', 'project_title', 'expert', 'expert_name',
                  'criterion', 'criterion_name', 'score', 'comment', 'created_at']


class ContestViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Contest.objects.annotate(project_count=Count('projects')).order_by('-created_at')
    serializer_class = ContestSerializer
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'end_date']

    @action(detail=True)
    def results(self, request, pk=None):
        contest = self.get_object()
        projects = list(contest.projects.exclude(status='draft').select_related('participant'))
        projects.sort(key=lambda p: (p.score_percent(), p.votes), reverse=True)
        data = [{'rank': i, 'id': p.id, 'title': p.title, 'participant': p.participant.username,
                 'score_percent': p.score_percent(), 'votes': p.votes}
                for i, p in enumerate(projects, 1)]
        return Response({'contest': contest.name, 'finalized': contest.results_finalized, 'results': data})


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.exclude(status='draft').select_related('contest', 'participant')
    serializer_class = ProjectSerializer
    search_fields = ['title', 'summary']
    ordering_fields = ['created_at', 'votes']
    http_method_names = ['get', 'post', 'head', 'options']

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticatedOrReadOnly()]

    def perform_create(self, serializer):
        if not is_participant(self.request.user):
            raise permissions.PermissionDenied('Создавать проекты могут только участники.')
        serializer.save(participant=self.request.user, status='draft')

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def vote(self, request, pk=None):
        project = self.get_object()
        if project.is_member(request.user):
            return Response({'detail': 'Нельзя голосовать за проект своей команды.'}, status=400)
        vote, created = ProjectVote.objects.get_or_create(project=project, user=request.user)
        if not created:
            vote.delete()
        project.votes = project.project_votes.count()
        project.save(update_fields=['votes'])
        return Response({'votes': project.votes, 'voted': created})


class EvaluationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Evaluation.objects.select_related('project', 'expert', 'criterion')
    serializer_class = EvaluationSerializer
    ordering_fields = ['created_at', 'score']


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        role = primary_role(request.user)
        info = ROLE_INFO.get(role, {})
        return Response({
            'username': request.user.username,
            'email': request.user.email,
            'full_name': request.user.get_full_name(),
            'role': role,
            'role_label': info.get('label'),
            'achievements': request.user.achievements.count(),
        })
