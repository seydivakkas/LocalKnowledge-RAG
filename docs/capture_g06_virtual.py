"""Produce an actual Tk UI screenshot using synthetic PDF, on Xvfb only."""
import os
import tempfile
from pathlib import Path
import time
from reportlab.pdfgen.canvas import Canvas
from PIL import ImageGrab
from localknowledge.application import AppServices
from localknowledge.ui.app import LocalKnowledgeApp
from localknowledge.ui.routes import RouteId

base=Path(tempfile.mkdtemp(prefix='lk_g06_capture_'))
pdf=base/'Sentetik_Kaynak_Kaniti.pdf'
cv=Canvas(str(pdf),pagesize=(600,800))
cv.setFont('Helvetica-Bold',18)
cv.drawString(72,740,'LOCALKNOWLEDGE - SENTETIK KANIT')
cv.setFont('Helvetica',13)
cv.drawString(72,690,'Mimari kaynak arama ve belge baglantisi.')
cv.drawString(72,658,'Koridor planinda kaynak koordinati dogrulanir.')
cv.drawString(72,626,'PDF dosyasi degistirilmeden yerel diskte saklanir.')
cv.drawString(72,594,'Sari isaret yalniz guvenilir eslesmede gorunur.')
cv.showPage()
cv.setFont('Helvetica-Bold',16)
cv.drawString(72,740,'IKINCI SAYFA - EK BILGI')
cv.drawString(72,680,'Bu sayfada onceki kaynak isareti gosterilmez.')
cv.save()
root=base/'data'
services=AppServices(root=root)
services.intake.import_document(pdf)
from localknowledge.jobs.runner import Runner
assert Runner(root).run_one()
hits=services.search.search('Koridor')
assert len(hits)==1
app=LocalKnowledgeApp(services=services)
app.geometry('1440x900+25+25')
app.source_chunk_id=hits[0].chunk_id
app.source_query="Koridor"
app.open_route(RouteId.SOURCE)
end=time.monotonic()+15
while time.monotonic()<end:
    app.update()
    if app.source_panel.preview is not None:break
    time.sleep(.025)
assert app.source_panel.preview is not None
assert app.source_panel.preview.geometry_status=='VERIFIED',app.source_panel.preview.detail
app.update();time.sleep(.7);app.update()
output=Path(__file__).parent/'screenshots'/'g06_verified_pdf_source_linux_virtual_1440x900.png'
ImageGrab.grab(bbox=(app.winfo_rootx(),app.winfo_rooty(),app.winfo_rootx()+app.winfo_width(),app.winfo_rooty()+app.winfo_height())).save(output)
print(output,output.stat().st_size,'source:',app.source_panel.preview.geometry_status,len(app.source_panel.preview.highlight_boxes))
app.source_panel.move(+1)
end=time.monotonic()+15
while time.monotonic()<end:
    app.update()
    if app.source_panel.preview is not None and app.source_panel.preview.page_number==2:break
    time.sleep(.025)
assert app.source_panel.preview.page_number==2 and not app.source_panel.preview.highlight_boxes
app.update();time.sleep(.5);app.update()
output2=Path(__file__).parent/'screenshots'/'g06_context_page_no_highlight.png'
ImageGrab.grab(bbox=(app.winfo_rootx(),app.winfo_rooty(),app.winfo_rootx()+app.winfo_width(),app.winfo_rooty()+app.winfo_height())).save(output2)
print(output2,output2.stat().st_size,'source:',app.source_panel.preview.geometry_status)
app.services.runner.stop()
app.destroy()
