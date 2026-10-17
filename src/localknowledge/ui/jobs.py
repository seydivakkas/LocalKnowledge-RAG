"""Real G04 queue screen. Only the Tk event thread manipulates widgets."""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from .components import Card, text
from .routes import RouteId
from .theme import TOKENS,accessible_button

NAMES={'PENDING':'Bekliyor','RUNNING':'İşleniyor','FAILED':'Hata','COMPLETED':'Metin hazır',
       'INTERRUPTED':'Kesildi','CANCELLED':'İptal edildi','SUPERSEDED':'Eski sürüm'}

class JobsPanel(tk.Frame):
    def __init__(self,parent,*,app):
        super().__init__(parent,bg=TOKENS['canvas'])
        self.app=app
        self._timer=None
        card=Card(self);card.pack(fill='both',expand=True)
        text(card.inner,'Asenkron Metin Çıkarma İşleri',size=16,weight='bold').pack(anchor='w')
        text(card.inner,'İşler SQLite üzerinde kalıcıdır. Metin hazır olması aranabilir olduğu anlamına gelmez (G05 bekleniyor).',
             color=TOKENS['muted'],size=9).pack(anchor='w',pady=(4,13))
        tool=tk.Frame(card.inner,bg=TOKENS['card']);tool.pack(fill='x',pady=(0,8))
        accessible_button(tool,'Yenile',self.refresh).pack(side='left',padx=(0,7))
        accessible_button(tool,'Seçileni İptal Et',self.cancel).pack(side='left',padx=(0,7))
        accessible_button(tool,'Yeniden Kuyruğa Al',self.retry).pack(side='left',padx=(0,7))
        accessible_button(tool,'Belge Kütüphanesi',lambda:self.app.open_route(RouteId.LIBRARY)).pack(side='right')
        wrapper=tk.Frame(card.inner,bg=TOKENS['card']);wrapper.pack(fill='both',expand=True)
        fields=('id','name','revision','status','processed','attempt','error')
        self.table=ttk.Treeview(wrapper,columns=fields,show='headings',height=15,selectmode='browse')
        for field,label,width in [('id','İş',55),('name','Belge',240),('revision','Sürüm',70),
                                  ('status','Durum',125),('processed','İlerleme',120),('attempt','Deneme',70),('error','Hata Kodu',190)]:
            self.table.heading(field,text=label)
            self.table.column(field,width=width,stretch=(field=='name'),anchor='w')
        self.table.pack(side='left',fill='both',expand=True)
        scrollbar=ttk.Scrollbar(wrapper,orient='vertical',command=self.table.yview)
        self.table.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right',fill='y')
        self.progress=ttk.Progressbar(card.inner,maximum=100,mode='determinate')
        self.progress.pack(fill='x',pady=(12,6))
        self.status=text(card.inner,'',size=9,color=TOKENS['muted'])
        self.status.pack(anchor='w')
        self.table.bind('<<TreeviewSelect>>',lambda _e:self.show_selected())
        self.bind('<Destroy>',self._destroyed,add='+')
        self.refresh()
        self._schedule()

    def _destroyed(self,event):
        if event.widget is self and self._timer is not None:
            try:self.after_cancel(self._timer)
            except tk.TclError:pass
            self._timer=None

    def _schedule(self):
        if self.winfo_exists():self._timer=self.after(900,self._tick)

    def _tick(self):
        self._timer=None
        if self.winfo_exists():
            self.refresh()
            self._schedule()

    def selected_id(self):
        selected=self.table.selection()
        return int(selected[0]) if selected else None

    def show_selected(self):
        job_id=self.selected_id()
        if job_id is None:return
        j=next((r for r in self.app.services.jobs.list() if r.id==job_id),None)
        if j:
            ratio=(j.processed_units*100/j.total_units) if j.total_units else 0
            self.progress['value']=ratio
            self.status.configure(text=f'İş #{j.id} · {NAMES[j.status]} · {j.processed_units}/{j.total_units} birim · {j.error_code or "Hata yok"}')

    def refresh(self):
        try:
            old=self.selected_id();jobs=self.app.services.jobs.list()
            for i in self.table.get_children():self.table.delete(i)
            for j in jobs:
                self.table.insert('', 'end',iid=str(j.id),values=(j.id,j.name,f'v{j.revision}',NAMES[j.status],
                                  f'{j.processed_units}/{j.total_units}',j.attempt,j.error_code or '—'))
            if old is not None and self.table.exists(str(old)):
                self.table.selection_set(str(old));self.show_selected()
            elif jobs:self.status.configure(text=f'{len(jobs)} kalıcı iş · Dış sunucu veya bulut kullanılmıyor.')
            else:self.status.configure(text='Henüz belge işi yok. Önce Belge Ekle bölümünü kullanın.')
        except Exception as exc:
            self.status.configure(text=f'İş kuyruğu açılamadı: {type(exc).__name__}')

    def cancel(self):
        job_id=self.selected_id()
        if job_id is not None:
            self.app.services.runner.request_cancel(job_id)
            self.refresh()

    def retry(self):
        job_id=self.selected_id()
        if job_id is not None:
            result=self.app.services.jobs.retry(job_id)
            self.status.configure(text='Yeniden sıraya alındı.' if result else 'Bu iş şu anda yeniden sıraya alınamaz.')
            self.refresh()


def show_jobs(app):
    app._page_header('Kalıcı iş kuyruğu · asenkron PDF/DOCX/TXT metin çıkarma · G05 FTS5 araması etkin')
    app.jobs_panel=JobsPanel(app.content,app=app)
    app.jobs_panel.pack(fill='both',expand=True,padx=30,pady=(0,25))
