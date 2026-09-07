"""Print-ready work reports with company, project and daily breakdowns."""
from datetime import date, datetime, timedelta
from pathlib import Path
import os
import tempfile
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


INK = colors.HexColor('#172D40')
TEAL = colors.HexColor('#087F8C')
MUTED = colors.HexColor('#596C7C')
PALE = colors.HexColor('#EDF5F6')
LINE = colors.HexColor('#DAE3E9')


def duration(seconds):
    seconds = max(0, int(seconds))
    return f'{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}'


def export_pdf(report, output=None, company=None, project=None):
    regular = Path('/usr/share/fonts/noto/NotoSans-Regular.ttf')
    bold = Path('/usr/share/fonts/noto/NotoSans-Bold.ttf')
    normal_font, bold_font = 'Helvetica', 'Helvetica-Bold'
    if regular.exists() and bold.exists():
        if 'TrackerSans' not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont('TrackerSans', str(regular)))
            pdfmetrics.registerFont(TTFont('TrackerSans-Bold', str(bold)))
        normal_font, bold_font = 'TrackerSans', 'TrackerSans-Bold'
    generated = datetime.now(ZoneInfo(report['timezone']))
    if output:
        path = Path(output).expanduser().resolve()
        if path.suffix.lower() != '.pdf':
            raise ValueError('PDF output filename must end in .pdf.')
    else:
        folder = Path.home() / 'Documents' / 'Time Tracker Reports'
        path = folder / f"time-report-{report['period']}-{report['start']}-{generated.strftime('%Y%m%d-%H%M%S-%f')}.pdf"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValueError('That PDF already exists. Choose a new filename.')

    body = ParagraphStyle('Body', fontName=normal_font, fontSize=9, leading=14, textColor=INK)
    small = ParagraphStyle('Small', parent=body, fontSize=8, leading=12, textColor=MUTED)
    heading = ParagraphStyle('Section', parent=body, fontName=bold_font, fontSize=13, leading=18, spaceBefore=20, spaceAfter=9, keepWithNext=True)
    title = ParagraphStyle('Title', parent=body, fontName=bold_font, fontSize=29, leading=35, spaceAfter=8)
    number = ParagraphStyle('Number', parent=body, alignment=TA_RIGHT)
    white = ParagraphStyle('White', parent=body, fontName=bold_font, textColor=colors.white, fontSize=8)
    def para(value, style=body):
        return Paragraph(escape(str(value)), style)

    width = A4[0] - 100
    story = [para('WORK / TIME REPORT', ParagraphStyle('Eyebrow', parent=small, textColor=TEAL, fontName=bold_font, spaceAfter=14)),
             para(report['period'].capitalize() + ' work report', title)]
    last_day = date.fromisoformat(report['end_exclusive']) - timedelta(days=1)
    start_day = date.fromisoformat(report['start'])
    period_label = start_day.strftime('%d %B %Y')
    if start_day != last_day:
        period_label += ' - ' + last_day.strftime('%d %B %Y')
    story += [para(period_label, ParagraphStyle('Period', parent=body, fontSize=12, leading=18, textColor=MUTED)), Spacer(1, 8),
              para('Scope: ' + (company or 'All companies') + (' / ' + project if project else ''), body), Spacer(1, 20)]

    metrics = [('TOTAL TIME', duration(report['total_seconds'])),
               ('ACTIVE DAYS', str(len({row['date'] for row in report['daily']}))),
               ('COMPANIES', str(len(report['companies'])))]
    cards = Table([[ [para(label, small), Spacer(1, 5), para(value, ParagraphStyle('Metric', parent=body, fontName=bold_font, fontSize=20, leading=26, textColor=TEAL))]
                    for label, value in metrics]], colWidths=[width * .46, width * .29, width * .25], hAlign='LEFT')
    cards.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), PALE), ('BOX', (0,0), (-1,-1), .5, LINE),
                               ('LEFTPADDING', (0,0), (-1,-1), 14), ('RIGHTPADDING', (0,0), (-1,-1), 10),
                               ('TOPPADDING', (0,0), (-1,-1), 13), ('BOTTOMPADDING', (0,0), (-1,-1), 13), ('VALIGN', (0,0), (-1,-1), 'TOP')]))
    story += [cards, Spacer(1, 9), para('Time is shown as hours:minutes:seconds. Decimal hours are provided for reference.', small)]
    if report['includes_running_timer']:
        story += [Spacer(1, 6), para('PROVISIONAL - Includes the active timer through ' + generated.strftime('%d %b %Y, %H:%M:%S') + '. The timer has not been stopped.', small)]

    def table_section(label, headers, rows, fractions, numeric=()):
        story.append(para(label, heading))
        data = [[para(h, white) for h in headers]]
        for row in rows:
            data.append([para(v, number if i in numeric else body) for i, v in enumerate(row)])
        table = Table(data, colWidths=[width * f for f in fractions], repeatRows=1, hAlign='LEFT')
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), INK), ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F5F8FA')]),
            ('VALIGN', (0,0), (-1,-1), 'TOP'), ('LEFTPADDING', (0,0), (-1,-1), 10), ('RIGHTPADDING', (0,0), (-1,-1), 10),
            ('TOPPADDING', (0,0), (-1,-1), 8), ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('LINEBELOW', (0,0), (-1,0), .5, INK), ('LINEBELOW', (0,-1), (-1,-1), .5, LINE)]))
        story.append(table)

    if report['companies']:
        total = report['total_seconds']
        table_section('01 / Company summary', ['Company', 'Time', 'Hours', 'Share'],
                      [(c['company'], duration(c['seconds']), f"{c['seconds']/3600:.2f}", f"{c['seconds']/total*100:.1f}%" if total else '0.0%') for c in report['companies']],
                      [.46, .23, .15, .16], (1,2,3))
        table_section('02 / Project breakdown', ['Company / project', 'Time', 'Hours'],
                      [(p['company'] + ' / ' + (p['project'] or 'General company time'), duration(p['seconds']), f"{p['seconds']/3600:.2f}") for p in report['projects']],
                      [.59,.25,.16], (1,2))
        table_section('03 / Daily detail', ['Date', 'Company / project', 'Time'],
                      [(date.fromisoformat(d['date']).strftime('%d %b %Y'), d['company'] + ' / ' + (d['project'] or 'General company time'), duration(d['seconds'])) for d in report['daily']],
                      [.23,.52,.25], (2,))
    else:
        story += [para('No time recorded', heading), para('There are no work records matching this period and selection.')]
    story += [Spacer(1, 18), para('Reporting notes', heading),
              para('Timezone: ' + report['timezone'] + '. Weeks run Monday through Sunday. Sessions crossing midnight are split into their local calendar days. Company and project tables describe the same time; do not add their totals together.', small),
              Spacer(1, 5), para('Decimal hours are rounded to two places; time values are displayed to the completed second. Small rounding differences can occur when adding displayed rows.', small)]

    def page(canvas, doc):
        canvas.saveState()
        canvas.setTitle(report['period'].capitalize() + ' work report - ' + report['start'])
        canvas.setAuthor('Time Tracker')
        canvas.setFillColor(TEAL)
        canvas.rect(0, A4[1]-7, A4[0], 7, fill=1, stroke=0)
        if doc.page > 1:
            canvas.setFont(bold_font, 8)
            canvas.setFillColor(MUTED)
            canvas.drawString(44, A4[1]-31, 'TIME TRACKER / ' + report['period'].upper() + ' REPORT')
        canvas.setStrokeColor(LINE)
        canvas.line(44, 43, A4[0]-44, 43)
        canvas.setFont(normal_font, 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(44, 29, 'Generated ' + generated.strftime('%d %b %Y at %H:%M') + ' | ' + report['timezone'])
        canvas.drawRightString(A4[0]-44, 29, f'TIME TRACKER  /  {doc.page}')
        canvas.restoreState()

    # Publish only a fully built PDF, without overwriting previous exports.
    fd, temporary = tempfile.mkstemp(prefix='.time-report-', suffix='.pdf', dir=path.parent)
    os.close(fd)
    try:
        doc = SimpleDocTemplate(temporary, pagesize=A4, leftMargin=44, rightMargin=44, topMargin=49, bottomMargin=61)
        doc.build(story, onFirstPage=page, onLaterPages=page)
        os.link(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return str(path)
