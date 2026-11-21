"""PDF-протокол результатов конкурса (fpdf2, DejaVu Sans — кириллица, обычный + жирный)."""
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from fpdf import FPDF
from fpdf.enums import XPos, YPos

FONT_DIR = Path(settings.BASE_DIR) / 'static' / 'fonts'
INDIGO = (99, 102, 241)


class ResultsPDF(FPDF):
    def header(self):
        self.set_font('Russo', '', 11)
        self.set_text_color(*INDIGO)
        self.cell(0, 7, 'КОНКУРС ПРОЕКТОВ', new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
        self.set_font('DejaVu', 'B', 15)
        self.set_text_color(30, 41, 59)
        self.cell(0, 9, 'Протокол результатов конкурса',
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
        self.set_draw_color(*INDIGO)
        self.set_line_width(0.6)
        self.line(self.l_margin, self.get_y() + 1, self.w - self.r_margin, self.get_y() + 1)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('DejaVu', '', 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f'Страница {self.page_no()}/{{nb}}', align='C')


def _table(pdf, widths, headers, rows, font_size=9):
    pdf.set_font('DejaVu', 'B', font_size)
    pdf.set_fill_color(238, 242, 255)
    pdf.set_text_color(30, 41, 59)
    for w, h in zip(widths, headers):
        pdf.cell(w, 8, h, border=1, align='C', fill=True)
    pdf.ln()
    pdf.set_font('DejaVu', '', font_size)
    for i, row in enumerate(rows):
        pdf.set_fill_color(245, 247, 255) if i % 2 else pdf.set_fill_color(255, 255, 255)
        for w, val in zip(widths, row):
            pdf.cell(w, 7, str(val), border=1, fill=True)
        pdf.ln()


def generate_results_pdf(contest):
    pdf = ResultsPDF()
    pdf.add_font('DejaVu', '', str(FONT_DIR / 'DejaVuSans.ttf'))
    pdf.add_font('DejaVu', 'B', str(FONT_DIR / 'DejaVuSans-Bold.ttf'))
    pdf.add_font('Russo', '', str(FONT_DIR / 'RussoOne-Regular.ttf'))
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    pdf.set_fill_color(*INDIGO)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('DejaVu', 'B', 13)
    pdf.cell(0, 11, '  ' + contest.name, new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)
    pdf.set_font('DejaVu', '', 10)
    pdf.multi_cell(0, 6, contest.description)
    pdf.ln(2)
    pdf.cell(0, 6, f'Период проведения: {contest.start_date:%d.%m.%Y} — {contest.end_date:%d.%m.%Y}',
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    organizer = contest.organizer.get_full_name() or contest.organizer.username
    pdf.cell(0, 6, f'Организатор: {organizer}', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if contest.finalized_at:
        pdf.cell(0, 6, f'Итоги подведены: {contest.finalized_at:%d.%m.%Y %H:%M}',
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    # Итоговая таблица: при подведённых итогах — из замороженного снапшота.
    snapshot = getattr(contest, 'result_snapshot', None) if contest.results_finalized else None
    if snapshot is not None:
        rows = [[r['rank'], r['title'][:34], r['participant'][:19],
                 r['score_percent'], r['votes'], r['status'][:20]] for r in snapshot.data]
    else:
        projects = list(contest.projects.exclude(status='draft').select_related('participant'))
        projects.sort(key=lambda p: (p.weighted_score_percent(), p.votes), reverse=True)
        rows = [[i, p.title[:34], p.participant.username[:19],
                 p.weighted_score_percent(), p.votes, p.get_status_display()[:20]]
                for i, p in enumerate(projects, 1)]
    pdf.set_font('DejaVu', 'B', 11)
    pdf.cell(0, 8, 'Итоговый рейтинг', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    _table(pdf, [12, 68, 38, 22, 20, 30],
           ['№', 'Проект', 'Участник', 'Балл, %', 'Голоса', 'Статус'], rows)
    if not rows:
        pdf.cell(0, 8, 'Проекты не подавались.', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Разбивка по критериям (средний % по каждому критерию).
    criteria = list(contest.criteria.all())
    projects = list(contest.projects.exclude(status='draft').prefetch_related('evaluations__criterion'))
    if criteria and projects:
        pdf.ln(5)
        pdf.set_font('DejaVu', 'B', 11)
        pdf.cell(0, 8, 'Оценки по критериям, %', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        shown = criteria[:6]
        col_w = (190 - 55) / len(shown)
        headers = ['Проект'] + [c.name[:14] for c in shown]
        breakdown = []
        for p in projects:
            cells = [p.title[:30]]
            for c in shown:
                scores = [e.score / c.max_score * 100 for e in p.evaluations.all() if e.criterion_id == c.pk]
                cells.append(round(sum(scores) / len(scores), 1) if scores else '—')
            breakdown.append(cells)
        _table(pdf, [55] + [col_w] * len(shown), headers, breakdown, font_size=8)
        if len(criteria) > 6:
            pdf.set_font('DejaVu', '', 8)
            pdf.cell(0, 6, f'Показаны первые 6 из {len(criteria)} критериев.',
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(5)
    pdf.set_font('DejaVu', 'B', 10)
    pdf.cell(0, 7, 'Критерии оценки (веса):', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font('DejaVu', '', 9)
    for c in criteria:
        pdf.cell(0, 6, f'  - {c.name}: макс. {c.max_score}, вес {c.weight}',
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(10)
    pdf.set_font('DejaVu', '', 10)
    pdf.cell(0, 7, 'Организатор: ____________________ / ____________________',
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)
    pdf.cell(0, 7, 'Председатель жюри: ______________ / ____________________',
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)
    pdf.cell(0, 7, f'Дата составления: {timezone.localdate():%d.%m.%Y}',
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    response = HttpResponse(bytes(pdf.output()), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="results_{contest.pk}.pdf"'
    return response
