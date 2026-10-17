"""Developer-only: screenshot real Tk UI with synthetic fixtures on an Xvfb display."""
from pathlib import Path
from tempfile import TemporaryDirectory
from reportlab.pdfgen.canvas import Canvas
from PIL import ImageGrab
from localknowledge.application import AppServices
from localknowledge.ui.app import LocalKnowledgeApp
from localknowledge.ui.routes import RouteId

screens=Path(__file__).parent/'screenshots'
screens.mkdir(exist_ok=True)
with TemporaryDirectory() as tmp:
    base=Path(tmp)
    source=base/'demo'
    source.mkdir()
    pdf=source/'Sentetik_Proje_Notları.pdf'
    cv=Canvas(str(pdf));cv.drawString(100,700,'Sentetik proje belgesi, sayfa 1');cv.showPage();cv.drawString(100,700,'Sentetik belgenin 2. sayfasi');cv.save()
    txt=source/'Türkçe_İçerik_Kılavuzu.txt'
    txt.write_text('Bu belge tamamen sentetiktir.\nGerçek müşteri kaydı yoktur.\n', encoding='utf-8')
    services=AppServices(root=base/'localdata')
    services.intake.import_document(pdf)
    services.intake.import_document(txt)
    app=LocalKnowledgeApp(services=services)
    app.geometry('1440x900+30+30')
    app.update()
    def capture(route, filename):
        app.open_route(route)
        for _ in range(3): app.update()
        x,y=app.winfo_rootx(),app.winfo_rooty()
        w,h=app.winfo_width(),app.winfo_height()
        ImageGrab.grab(bbox=(x,y,x+w,y+h)).save(screens/filename)
    capture(RouteId.HOME,'g03_dashboard_linux_virtual_1440x900.png')
    capture(RouteId.LIBRARY,'g03_library_linux_virtual_1440x900.png')
    capture(RouteId.IMPORT,'g03_import_linux_virtual_1440x900.png')
    app.geometry('1100x720+30+30')
    capture(RouteId.LIBRARY,'g03_library_linux_virtual_1100x720.png')
    app.destroy()
print('Synthetic-only screenshots:',*[str(x.name) for x in sorted(screens.glob('g03_*'))])
