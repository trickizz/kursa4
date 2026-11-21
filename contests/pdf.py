"""Генерация PDF-протокола результатов конкурса (fpdf2, шрифт Play с кириллицей)."""
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse
from fpdf import FPDF
from fpdf.enums import XPos, YPos

FONT_DIR = Path(settings.BASE_DIR) / 'static' / 'fonts'


class ResultsPDF(FPDF):
    def header(self):
        self.set_font('DejaVu', 'B', 14)
        self.cell(0, 10, 'Протокол результатов конкурса',
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
        self.ln(2)

    def footer(self):
        self.set_y(-15)
        self.set_font('DejaVu', '', 8)
        self.cell(0, 10, f'Страница {self.page_no()}/{{nb}}', align='C')


def generate_results_pdf(contest):
    pdf = ResultsPDF()
    pdf.add_font('DejaVu', '', str(FONT_DIR / 'Play-Regular.ttf'))
    pdf.add_font('DejaVu', 'B', str(FONT_DIR / 'Play-Bold.ttf'))
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    pdf.set_font('DejaVu', 'B', 13)
    pdf.cell(0, 9, contest.name, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
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

    projects = list(contest.projects.exclude(status='draft').select_related('participant'))
    projects.sort(key=lambda p: (p.score_percent(), p.votes), reverse=True)

    widths = [12, 68, 38, 22, 20, 30]
    headers = ['№', 'Проект', 'Участник', 'Балл, %', 'Голоса', 'Статус']
    pdf.set_font('DejaVu', 'B', 9)
    pdf.set_fill_color(238, 242, 255)
    for w, h in zip(widths, headers):
        pdf.cell(w, 8, h, border=1, align='C', fill=True)
    pdf.ln()
    pdf.set_font('DejaVu', '', 9)
    for i, p in enumerate(projects, 1):
        row = [str(i), p.title[:36], p.participant.username[:20],
               str(p.score_percent()), str(p.votes), p.get_status_display()[:16]]
        for w, val in zip(widths, row):
            pdf.cell(w, 7, val, border=1)
        pdf.ln()
    if not projects:
        pdf.cell(0, 8, 'Проекты не подавались.', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(8)
    pdf.set_font('DejaVu', '', 10)
    pdf.cell(0, 7, 'Подпись организатора: ________________________',
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    response = HttpResponse(bytes(pdf.output()), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="results_{contest.pk}.pdf"'
    return response
