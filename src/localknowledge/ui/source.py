"""G07 isolated original-page viewer. Tk never receives an unverified highlight."""
from __future__ import annotations
import io
import queue
import threading
import tkinter as tk
from tkinter import ttk

from ..viewer.service import SourceViewError
from .components import Card, text
from .theme import TOKENS


class SourcePanel(tk.Frame):
    def __init__(self,parent,*,app):
        super().__init__(parent,bg=TOKENS['canvas'])
        self.app=app
        self.chunk_id=getattr(app,'source_chunk_id',None)
        self.current_page=None
        self.current_scale=1.25
        self.preview=None
        self._events=queue.Queue()
        self._timer=None
        self._busy=False
        self._pil_image=None
        self._tk_image=None
        self._canvas_timer=None
        bar=Card(self);bar.pack(fill='x',pady=(0,12))
        tools=tk.Frame(bar.inner,bg=TOKENS['card']);tools.pack(fill='x')
        self.label=text(tools,'Özgün belge kaynağı',size=12,weight='bold')
        self.label.pack(side='left')
        self.back=ttk.Button(tools,text='‹ Önceki Sayfa',command=lambda:self.move(-1))
        self.back.pack(side='right',padx=(6,0))
        self.next=ttk.Button(tools,text='Sonraki Sayfa ›',command=lambda:self.move(1))
        self.next.pack(side='right',padx=(6,0))
        self.zoom_out=ttk.Button(tools,text='−',width=3,command=lambda:self.zoom(-.25))
        self.zoom_out.pack(side='right',padx=(6,0))
        self.zoom_in=ttk.Button(tools,text='+',width=3,command=lambda:self.zoom(.25))
        self.zoom_in.pack(side='right',padx=(6,0))
        self.status=text(self,'Kaynak seçin; yalnız doğrulanabilen konumlar sarı işaretlenir.',size=10,
                         color=TOKENS['muted'],bg=TOKENS['canvas'])
        self.status.pack(anchor='w',pady=(0,12))
        body=tk.PanedWindow(self,orient='horizontal',bg=TOKENS['canvas'],sashwidth=6,bd=0)
        body.pack(fill='both',expand=True)
        left=Card(body)
        canvas_frame=tk.Frame(left.inner,bg=TOKENS['soft'])
        canvas_frame.pack(fill='both',expand=True)
        self.canvas=tk.Canvas(canvas_frame,bg='#dfe7f0',highlightthickness=0,width=650,height=580)
        vbar=ttk.Scrollbar(canvas_frame,orient='vertical',command=self.canvas.yview)
        hbar=ttk.Scrollbar(canvas_frame,orient='horizontal',command=self.canvas.xview)
        self.canvas.configure(xscrollcommand=hbar.set,yscrollcommand=vbar.set,takefocus=True)
        self.canvas.bind('<Prior>',lambda e:self._shortcut_move(-1))
        self.canvas.bind('<Next>',lambda e:self._shortcut_move(1))
        self.canvas.bind('<Alt-Left>',lambda e:self._shortcut_move(-1))
        self.canvas.bind('<Alt-Right>',lambda e:self._shortcut_move(1))
        self.canvas.bind('<Control-plus>',lambda e:self._shortcut_zoom(.25))
        self.canvas.bind('<Control-minus>',lambda e:self._shortcut_zoom(-.25))
        self.canvas.bind('<Control-0>',lambda e:self._shortcut_reset())
        canvas_frame.rowconfigure(0,weight=1)
        canvas_frame.columnconfigure(0,weight=1)
        self.canvas.grid(row=0,column=0,sticky='nsew')
        vbar.grid(row=0,column=1,sticky='ns')
        hbar.grid(row=1,column=0,sticky='ew')
        self.canvas.bind('<Configure>',self._request_redraw)
        right=Card(body)
        text(right.inner,'Kaynak Kanıtı',size=14,weight='bold').pack(anchor='w',pady=(0,8))
        self.metadata=text(right.inner,'Aramadan bir sonuç açın.',size=9,color=TOKENS['muted'],wrap=390)
        self.metadata.pack(anchor='w',pady=(0,10))
        self.quote=tk.Text(right.inner,font=('Segoe UI',10),wrap='word',height=18,
                           bd=0,background='#f4f7fb',padx=12,pady=12)
        self.quote.pack(fill='both',expand=True)
        self.quote.configure(state='disabled')
        body.add(left,minsize=380,stretch='always')
        body.add(right,minsize=260)
        self.bind('<Destroy>',self._on_destroy,add='+')
        self._set_buttons()
        self._poll()
        if self.chunk_id is not None:
            self.load()
        else:
            self.status.configure(text='Arama sonuçlarından doğrulanmış bir kaynak seçin.')

    def _on_destroy(self,event):
        if event.widget is not self:return
        for ident in (self._timer,self._canvas_timer):
            if ident is not None:
                try:self.after_cancel(ident)
                except tk.TclError:pass
        self._timer=self._canvas_timer=None

    def _set_buttons(self):
        active=self.preview is not None and self.preview.page_count is not None and not self._busy
        pg=self.preview.page_number if active else 0
        count=self.preview.page_count if active else 0
        self.back.configure(state='normal' if active and pg>1 else 'disabled')
        self.next.configure(state='normal' if active and pg<count else 'disabled')
        self.zoom_in.configure(state='normal' if active and self.current_scale<2 else 'disabled')
        self.zoom_out.configure(state='normal' if active and self.current_scale>.5 else 'disabled')

    def load(self):
        if self._busy or self.chunk_id is None:return
        self._busy=True
        self._set_buttons()
        self.status.configure(text='Yerel arşiv ve kaynak koordinatları doğrulanıyor…')
        chunk=self.chunk_id;page=self.current_page;scale=self.current_scale
        svc=self.app.services.viewer
        mailbox=self._events
        def job():
            try:value=svc.open(chunk,page_number=page,scale=scale,highlight_query=getattr(self.app,'source_query',None))
            except SourceViewError as e:value=e
            except Exception:value=SourceViewError('UNEXPECTED_VIEWER_ERROR','Kaynak görüntüleme başarısız.')
            mailbox.put(value)
        threading.Thread(target=job,daemon=True,name='LK-G07-Viewer').start()

    def _poll(self):
        if not self.winfo_exists():return
        try:
            while True:
                result=self._events.get_nowait()
                self._busy=False
                if isinstance(result,Exception):
                    self.preview=None
                    self._pil_image=None
                    self.canvas.delete('all')
                    self.status.configure(text=f'Kaynak açılamadı · {result.code}: {result}')
                else:
                    self.preview=result
                    self.current_page=result.page_number
                    self.label.configure(text=f'{result.hit.name}  ·  Kaynak {result.page_number}' +
                                            (f' / {result.page_count}' if result.page_count else ''))
                    self.status.configure(text=('DOĞRULANMIŞ KONUM · ' if result.geometry_status=='VERIFIED' else
                        'KONUM DOĞRULANAMADI · ' if result.geometry_status=='UNVERIFIED_POSITION' else 'DOĞRULANMIŞ METİN · ')+result.detail)
                    self.metadata.configure(text=f'{result.hit.source_label}\nBelge SHA-256: {result.hit.sha256}\n'
                        f'İşaretleme: {result.geometry_status}\nBu içerik yalnız yerel diskte işlenir.')
                    self.quote.configure(state='normal')
                    self.quote.delete('1.0','end')
                    self.quote.insert('1.0',result.original_unit)
                    self.quote.tag_add('match',f'1.0+{result.quote_start}c',f'1.0+{result.quote_end}c')
                    self.quote.tag_configure('match',background='#fff0a8',foreground='#18243c')
                    self.quote.see(f'1.0+{result.quote_start}c')
                    self.quote.configure(state='disabled')
                    if result.image_png:
                        from PIL import Image
                        self._pil_image=Image.open(io.BytesIO(result.image_png)).copy()
                    else:self._pil_image=None
                    self._redraw()
                self._set_buttons()
        except queue.Empty:pass
        self._timer=self.after(80,self._poll)

    def _request_redraw(self,_event=None):
        if self._canvas_timer is not None:
            try:self.after_cancel(self._canvas_timer)
            except tk.TclError:pass
        self._canvas_timer=self.after(75,self._redraw)

    def _redraw(self):
        self._canvas_timer=None
        self.canvas.delete('all')
        if self._pil_image is None or self.preview is None:return
        from PIL import Image,ImageTk
        img=self._pil_image
        boundw=max(self.canvas.winfo_width()-24,120)
        boundh=max(self.canvas.winfo_height()-24,120)
        ratio=min(boundw/img.width,boundh/img.height,1.0)*(self.current_scale/1.25)
        display=img.resize((max(1,round(img.width*ratio)),max(1,round(img.height*ratio))),Image.Resampling.LANCZOS)
        self._tk_image=ImageTk.PhotoImage(display,master=self.canvas)
        xx=max(0,(self.canvas.winfo_width()-display.width)//2)
        yy=max(0,(self.canvas.winfo_height()-display.height)//2)
        self.canvas.create_image(xx,yy,image=self._tk_image,anchor='nw')
        self.canvas.configure(scrollregion=(0,0,max(xx+display.width+12,self.canvas.winfo_width()),max(yy+display.height+12,self.canvas.winfo_height())))
        if self.preview.geometry_status=='VERIFIED':
            for box in self.preview.highlight_boxes:
                self.canvas.create_rectangle(xx+box.left*display.width,yy+box.top*display.height,
                    xx+box.right*display.width,yy+box.bottom*display.height,
                    fill='#f3ca40',outline='',stipple='gray50',tags=('verified-highlight',))

    def _shortcut_move(self,delta):
        self.move(delta)
        return 'break'

    def _shortcut_zoom(self,delta):
        self.zoom(delta)
        return 'break'

    def _shortcut_reset(self):
        if self.preview and not self._busy:
            self.current_scale=1.25
            self.load()
        return 'break'

    def move(self,delta:int):
        if self.preview and self.preview.page_count and not self._busy:
            candidate=self.preview.page_number+delta
            if 1<=candidate<=self.preview.page_count:
                self.current_page=candidate;self.load()

    def zoom(self,increment:float):
        if self.preview and self.preview.page_count and not self._busy:
            self.current_scale=max(.5,min(2.0,round(self.current_scale+increment,2)))
            self.load()


def show_source(app):
    app._page_header('Özgün PDF sayfası ve doğrulanabilir geometrik işaretleme · G07')
    app.source_panel=SourcePanel(app.content,app=app)
    app.source_panel.pack(fill='both',expand=True,padx=30,pady=(0,20))
