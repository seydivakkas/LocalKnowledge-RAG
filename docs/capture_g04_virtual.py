"""Real Tk screenshot capture, Linux Xvfb, synthetic files only."""
from pathlib import Path
from tempfile import TemporaryDirectory
from PIL import ImageGrab
from localknowledge.application import AppServices
from localknowledge.ui.app import LocalKnowledgeApp
from localknowledge.ui.routes import RouteId
import time

screens=Path(__file__).parent/'screenshots'
screens.mkdir(exist_ok=True)
with TemporaryDirectory() as td:
    base=Path(td)
    sources=base/'source';sources.mkdir()
    for i in range(3):
        (sources/f'Ornek_Belge_{i+1}.txt').write_text(f'Bu sentetik belge {i+1} için içeriktir.\nKaynak doğrulama örneği.\n',encoding='utf-8')
    services=AppServices(root=base/'data')
    for path in sorted(sources.glob('*.txt')):services.intake.import_document(path)
    app=LocalKnowledgeApp(services=services)
    app.geometry('1440x900+30+30');app.update()
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        app.update();time.sleep(.06)
        if all(j.status=='COMPLETED' for j in services.jobs.list()):break
    assert all(j.status=='COMPLETED' for j in services.jobs.list())
    def capture(route,name):
        app.open_route(route)
        for _ in range(3):app.update()
        x,y=app.winfo_rootx(),app.winfo_rooty()
        w,h=app.winfo_width(),app.winfo_height()
        ImageGrab.grab(bbox=(x,y,x+w,y+h)).save(screens/name)
    capture(RouteId.JOBS,'g04_jobs_linux_virtual_1440x900.png')
    capture(RouteId.HOME,'g04_dashboard_linux_virtual_1440x900.png')
    capture(RouteId.LIBRARY,'g04_library_linux_virtual_1440x900.png')
    app.geometry('1100x720+30+30')
    capture(RouteId.JOBS,'g04_jobs_linux_virtual_1100x720.png')
    services.runner.stop();app.destroy()
print('Captured:',*[x.name for x in sorted(screens.glob('g04_*.png'))])
