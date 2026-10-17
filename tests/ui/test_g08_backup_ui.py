"""G08 real Tk window with async backing services in Xvfb/interactive display."""
import tempfile
import time
import tkinter as tk
from pathlib import Path
import unittest

from localknowledge.application import AppServices
from localknowledge.ui.app import LocalKnowledgeApp
from localknowledge.ui.routes import RouteId


class BackupUiTests(unittest.TestCase):
    def test_async_backup_and_reopen_in_new_directory(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            services=AppServices(root=root/'data')
            doc=root/'source.txt';doc.write_text('Kaynakları koruyan yerel arama.\n',encoding='utf-8')
            services.intake.import_document(doc)
            try:app=LocalKnowledgeApp(services=services)
            except tk.TclError as e:raise unittest.SkipTest(f'No graphical display: {e}')
            try:
                self.assertTrue(app.open_route(RouteId.BACKUP))
                panel=app.backup_panel
                self.assertTrue(all(str(b.cget('state'))=='normal' for b in panel.buttons))
                target=root/'new-backup'
                panel._start(services.backup.create,target)
                self.assertTrue(app.backup_busy)
                end=time.monotonic()+15
                while app.backup_busy and time.monotonic()<end:
                    app.update();time.sleep(.01)
                self.assertFalse(app.backup_busy)
                self.assertTrue((target/'manifest.json').exists())
                self.assertIn('tamamlandı',panel.status.cget('text'))
                destination=root/'restored'
                panel._start(services.backup.restore,target,destination)
                end=time.monotonic()+15
                while app.backup_busy and time.monotonic()<end:
                    app.update();time.sleep(.01)
                self.assertFalse(app.backup_busy)
                self.assertTrue((destination/'library.sqlite3').is_file())
            finally:
                services.runner.stop()
                app.destroy()

if __name__=='__main__':unittest.main()
