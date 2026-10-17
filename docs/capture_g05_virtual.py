"""Capture REAL Tkinter under Linux Xvfb; synthetic inputs, not Windows evidence."""
from pathlib import Path
from tempfile import TemporaryDirectory
from PIL import ImageGrab
from localknowledge.application import AppServices
from localknowledge.ui.app import LocalKnowledgeApp
from localknowledge.ui.routes import RouteId
import time

screens=Path(__file__).parent/'screenshots';screens.mkdir(exist_ok=True)
with TemporaryDirectory(prefix='g05-screens-') as td:
    base=Path(td);sources=base/'docs';sources.mkdir()
    topics=[
        ('Proje_Yonetim_Teknik_Sartname.txt','Mimari projede koridor genişliği en az yüz santimetre.\nYangın merdiveni kaçış kapısı projesi.\nYapı malzemesi ve teknik şartname gereksinimleri.\n'),
        ('Yapi_Analiz_Raporu.txt','Tasarım sürecinde cephe analizi ve sürdürülebilirlik.\nEnerji verimliliği ve doğal aydınlatma kontrolü.\n'),
        ('Ofis_Prosedurleri.txt','Müşteri teklif inceleme ve iş teslim takvimi.\nDijital belgelerin kaynak doğrulama kuralları.\n')
    ]
    services=AppServices(root=base/'store')
    for name,txt in topics:
        path=sources/name;path.write_text(txt,encoding='utf-8');services.intake.import_document(path)
    for _ in range(3):assert services.runner.run_one()
    app=LocalKnowledgeApp(services=services)
    app.geometry('1440x900+25+25')
    app.update()
    def capture(route,name,query=None):
        app.open_route(route)
        app.update()
        if query:
            panel=app.search_panel
            panel.query.set(query);panel.run_search()
            deadline=time.monotonic()+8
            while time.monotonic()<deadline and (panel._busy or not panel.table.get_children()):
                app.update();time.sleep(.05)
            assert panel.table.get_children(),f'No search result for {query}'
            panel.table.selection_set(panel.table.get_children()[0]);panel.table.focus(panel.table.get_children()[0]);app.update()
        for _ in range(4):app.update()
        x,y=app.winfo_rootx(),app.winfo_rooty();w,h=app.winfo_width(),app.winfo_height()
        ImageGrab.grab(bbox=(x,y,x+w,y+h)).save(screens/name)
    capture(RouteId.HOME,'g05_dashboard_linux_virtual_1440x900.png')
    capture(RouteId.SEARCH,'g05_search_linux_virtual_1440x900.png','koridor')
    app.search_panel.open_source()
    app.update()
    modal=next(w for w in app.search_panel.winfo_children() if w.winfo_class()=='Toplevel')
    modal.lift();modal.update()
    x,y=modal.winfo_rootx(),modal.winfo_rooty();w,h=modal.winfo_width(),modal.winfo_height()
    ImageGrab.grab(bbox=(x,y,x+w,y+h)).save(screens/'g05_verified_source_linux_virtual.png')
    modal.destroy()
    app.geometry('1100x720+25+25')
    capture(RouteId.SEARCH,'g05_search_linux_virtual_1100x720.png','yangın')
    services.runner.stop();app.destroy()
print('Captured:',*[f.name for f in sorted(screens.glob('g05_*.png'))])
