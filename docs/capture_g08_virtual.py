"""Actual G08 Tkinter screenshots with synthetic local text, only in Xvfb."""
from pathlib import Path
import tempfile,time
from PIL import ImageGrab
from localknowledge.application import AppServices
from localknowledge.ui.app import LocalKnowledgeApp
from localknowledge.ui.routes import RouteId

with tempfile.TemporaryDirectory(prefix='lk-g08-capture-') as folder:
    base=Path(folder);root=base/'data'
    fixture=base/'Sentetik_Belge.txt'
    fixture.write_text('Bu belge yalnız G08 yedekleme arayüzü örneğidir.\n',encoding='utf-8')
    services=AppServices(root=root)
    services.intake.import_document(fixture)
    app=LocalKnowledgeApp(services=services)
    app.geometry('1440x900+25+25')
    app.open_route(RouteId.BACKUP)
    app.update();time.sleep(.3);app.update()
    out=Path(__file__).parent/'screenshots'
    out.mkdir(exist_ok=True)
    def snap(path):
        app.update_idletasks()
        ImageGrab.grab(bbox=(app.winfo_rootx(),app.winfo_rooty(),app.winfo_rootx()+app.winfo_width(),
                             app.winfo_rooty()+app.winfo_height())).save(out/path)
    snap('g08_backup_ready_linux_virtual_1440x900.png')
    panel=app.backup_panel
    panel._start(services.backup.create,base/'yeni-yedek')
    deadline=time.monotonic()+15
    while app.backup_busy and time.monotonic()<deadline:
        app.update();time.sleep(.02)
    assert not app.backup_busy and (base/'yeni-yedek'/'manifest.json').exists()
    app.update();time.sleep(.4);app.update()
    snap('g08_backup_verified_linux_virtual_1440x900.png')
    print('PASS: actual UI, verified backup, screenshots')
    services.runner.stop();app.destroy()
