"""Development-only screenshot capture; no screenshot bundled as a passed Windows test."""
import sys
from pathlib import Path
from PIL import ImageGrab
from localknowledge.ui.app import LocalKnowledgeApp

out = Path(sys.argv[1])
geometry = sys.argv[2] if len(sys.argv)>2 else "1440x900"
app = LocalKnowledgeApp()
app.geometry(geometry + "+0+0")
app.update()
app.after(500, app.quit)
app.mainloop()
app.update_idletasks()
x, y = app.winfo_rootx(), app.winfo_rooty()
w, h = app.winfo_width(), app.winfo_height()
ImageGrab.grab(bbox=(x, y, x+w, y+h)).save(out)
print(out, w,h)
app.destroy()
