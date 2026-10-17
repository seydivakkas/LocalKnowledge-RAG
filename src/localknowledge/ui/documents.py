"""G03 real document library, version history and async intake Tk views."""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

from ..documents.repository import LibraryDocument
from ..ingest.parsers import IntakeError
from .components import Card, EmptyState, StatusPill, text
from .routes import RouteId
from .theme import TOKENS, FONT, accessible_button


def _size(n: int) -> str:
    return f'{n/1024/1024:.2f} MiB' if n >= 1024 * 1024 else f'{n/1024:.1f} KiB'


def _section(app, caption: str) -> tk.Frame:
    holder = tk.Frame(app.content, bg=TOKENS['canvas'])
    holder.pack(fill='x', padx=30, pady=(22, 15))
    text(holder, caption, bg=TOKENS['canvas'], color=TOKENS['muted'], size=10).pack(anchor='w')
    return holder


class LibraryPanel(tk.Frame):
    PAGE_SIZE = 50

    def __init__(self, parent, *, app):
        super().__init__(parent,bg=TOKENS['canvas'])
        self.app = app
        self.page = 0
        self.records: dict[str,LibraryDocument] = {}
        bar = tk.Frame(self,bg=TOKENS['canvas'])
        bar.pack(fill='x',pady=(0,14))
        self.query = tk.StringVar()
        self.entry = ttk.Entry(bar,textvariable=self.query,width=33)
        self.entry.pack(side='left',ipady=7,padx=(0,8))
        self.entry.bind('<Return>',lambda _e:self.search())
        self.kind = tk.StringVar(value='ALL')
        self.kind_box = ttk.Combobox(bar,textvariable=self.kind,values=['ALL','PDF','DOCX','TXT'],state='readonly',width=8)
        self.kind_box.pack(side='left',padx=5)
        self.kind_box.bind('<<ComboboxSelected>>',lambda _e:self.search())
        self.archived = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar,text='Arşivlenenler',variable=self.archived,command=self.search).pack(side='left',padx=7)
        accessible_button(bar,'Ara',self.search,primary=True).pack(side='left',padx=4)
        accessible_button(bar,'Belge Ekle',lambda:app.open_route(RouteId.IMPORT),primary=True).pack(side='right')
        card = Card(self)
        card.pack(fill='both',expand=True)
        text(card.inner,'Yerel Belge Kütüphanesi',size=15,weight='bold').pack(anchor='w')
        text(card.inner,'Kayıtlı özgünler, belge sürümleri ve gerçek FTS5 indeks durumu',size=9,color=TOKENS['muted']).pack(anchor='w',pady=(3,12))
        frame=tk.Frame(card.inner,bg=TOKENS['card'])
        frame.pack(fill='both',expand=True)
        cols=('name','kind','revision','scope','size','status','date')
        self.tree=ttk.Treeview(frame,columns=cols,show='headings',style='LK.Treeview',height=10,selectmode='browse')
        for key,label,width in [('name','Belge',170),('kind','Tür',55),('revision','Sürüm',50),('scope','Sayfa / Paragraf',125),('size','Boyut',75),('status','İndeks',75),('date','Kayıt',105)]:
            self.tree.heading(key,text=label)
            self.tree.column(key,width=width,stretch=(key=='name'),anchor='w')
        scroll=ttk.Scrollbar(frame,orient='vertical',command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side='left',fill='both',expand=True)
        scroll.pack(side='right',fill='y')
        self.tree.bind('<<TreeviewSelect>>',lambda _e:self._selected_changed())
        actions=tk.Frame(card.inner,bg=TOKENS['card'])
        actions.pack(fill='x',pady=(12,0))
        self.count_text=text(actions,'',size=9,color=TOKENS['muted'])
        self.count_text.pack(side='left')
        for title,cmd in [('Önceki',self.prev_page),('Sonraki',self.next_page),('Sürümler',self.versions),('Bütünlüğü Doğrula',self.verify),('Arşivle / Geri Al',self.archive)]:
            accessible_button(actions,title,cmd).pack(side='right',padx=(5,0))
        self.message=text(card.inner,'Bir belge seçin.',size=9,color=TOKENS['muted'])
        self.message.pack(anchor='w',pady=(12,0))
        self.refresh()

    def selected(self) -> LibraryDocument | None:
        selection=self.tree.selection()
        return self.records.get(selection[0]) if selection else None

    def _selected_changed(self):
        r=self.selected()
        if r:
            self.message.configure(text=f'Belge: {r.name}  ·  SHA-256: {r.sha256}  ·  ID: {r.document_id}')

    def search(self):
        self.page=0
        self.refresh()

    def refresh(self):
        try:
            rows=self.app.services.repository.list_documents(self.query.get(),self.kind.get(),self.archived.get(),self.PAGE_SIZE,self.page*self.PAGE_SIZE)
            count=self.app.services.repository.count_documents(self.query.get(),self.kind.get(),self.archived.get())
            self.records={r.document_id:r for r in rows}
            states=self.app.services.repository.extraction_statuses(tuple(self.records))
            for item in self.tree.get_children(): self.tree.delete(item)
            for r in rows:
                scope=f'{r.page_count} sayfa' if r.kind=='PDF' else f'{r.paragraph_count} paragraf'
                self.tree.insert('', 'end', iid=r.document_id,values=(r.name,r.kind,f'v{r.revision}',scope,_size(r.size_bytes),{'INDEXED':'Aranabilir','COMPLETED':'Metin hazır','RUNNING':'Çıkarılıyor','FAILED':'Hata','INTERRUPTED':'Kesildi','CANCELLED':'İptal','PENDING':'Bekliyor','SUPERSEDED':'Eski'} .get(states.get(r.document_id,'PENDING'),'Bekliyor'),r.updated_at[:16]))
            self.count_text.configure(text=f'{count} belge · Sayfa {self.page+1} · Gösterilen {len(rows)}')
            self.message.configure(text='Belge bulunamadı. Önce Belge Ekle işlemini kullanın.' if not rows else 'Bir belge seçin. Metin çıkarma kuyruğu G04 İş Kuyruğu ekranından izlenebilir; arama Kaynaklı Arama ekranında kullanılabilir.')
        except Exception as exc:
            self.message.configure(text=f'Kütüphane açılamadı: {exc}')

    def prev_page(self):
        if self.page>0:
            self.page-=1
            self.refresh()

    def next_page(self):
        if len(self.records)==self.PAGE_SIZE:
            self.page+=1
            self.refresh()
            if not self.records:
                self.page-=1
                self.refresh()

    def versions(self):
        selected=self.selected()
        if not selected:
            self.message.configure(text='Önce bir belge seçin.')
            return
        self.app.router.state.selected_document_id=selected.document_id
        self.app.open_route(RouteId.HISTORY)

    def archive(self):
        r=self.selected()
        if not r:
            self.message.configure(text='Önce bir belge seçin.')
            return
        if not messagebox.askyesno('Arşiv',f'{r.name} kaydı {"geri alınsın" if r.archived else "arşivlensin"}? Özgün içerik silinmeyecek.',parent=self):
            return
        self.app.services.repository.archive(r.document_id,not r.archived)
        self.refresh()

    def verify(self):
        r=self.selected()
        if not r:
            self.message.configure(text='Önce bir belge seçin.')
            return
        try:
            ok=self.app.services.intake.verify(r.document_id,r.revision)
            self.message.configure(text='Kaydedilmiş özgün kopya SHA-256: DOĞRULANDI.' if ok else 'UYARI: Kaydedilmiş kopya eksik veya SHA-256 uyuşmuyor.')
        except Exception as exc:
            self.message.configure(text=f'Bütünlük doğrulanamadı: {exc}')


class ImportPanel(tk.Frame):
    def __init__(self,parent,*,app):
        super().__init__(parent,bg=TOKENS['canvas'])
        self.app=app
        self.paths: tuple[str,...]=()
        self.busy=False
        self.result_queue:queue.Queue=queue.Queue()
        card=Card(self)
        card.pack(fill='both',expand=True)
        text(card.inner,'PDF, DOCX veya TXT ekleyin',size=16,weight='bold').pack(anchor='w')
        text(card.inner,'Özgün dosya yerinde korunur. SHA-256 ile yerel arşiv kopyası saklanır.',color=TOKENS['muted'],size=10).pack(anchor='w',pady=(5,13))
        buttons=tk.Frame(card.inner,bg=TOKENS['card'])
        buttons.pack(fill='x')
        self.choose_button=accessible_button(buttons,'Dosya Seç',self.choose)
        self.choose_button.pack(side='left',padx=(0,8))
        self.start_button=accessible_button(buttons,'Güvenli İçe Al',self.start,primary=True)
        self.start_button.pack(side='left')
        accessible_button(buttons,'Kütüphane',lambda:app.open_route(RouteId.LIBRARY)).pack(side='right')
        self.selected_label=text(card.inner,'Henüz dosya seçilmedi.',size=9,color=TOKENS['muted'])
        self.selected_label.pack(anchor='w',pady=(13,8))
        self.status_label=text(card.inner,'Hazır',size=10,color=TOKENS['primary'])
        self.status_label.pack(anchor='w',pady=(6,8))
        self.results=tk.Text(card.inner,height=14,wrap='word',font=(FONT,10),bg=TOKENS['soft'],relief='flat',state='disabled')
        self.results.pack(fill='both',expand=True)
        text(card.inner,'Not: Bu işlem belge kaydı oluşturur; metin çıkarma G04 kuyruğuna alınır; arama G05 sırasında eklenecek. Şifreli PDF desteklenmiyor.',size=9,color=TOKENS['muted'],wraplength=780,justify='left').pack(anchor='w',pady=(12,0))

    def choose(self):
        paths=filedialog.askopenfilenames(parent=self,title='Yerel belgeleri seçin',filetypes=[('Belgeler','*.pdf *.docx *.txt'),('PDF','*.pdf'),('Word','*.docx'),('Metin','*.txt')])
        if paths:
            self.set_files(paths)

    def set_files(self, paths):
        if self.busy:
            return
        self.paths=tuple(str(p) for p in paths)
        self.selected_label.configure(text=f'{len(self.paths)} dosya seçildi: '+', '.join(Path(p).name for p in self.paths[:3]))

    def _log(self, message):
        self.results.configure(state='normal')
        self.results.insert('end',message+'\n')
        self.results.see('end')
        self.results.configure(state='disabled')

    def start(self):
        if self.busy:
            return
        if not self.paths:
            self.status_label.configure(text='Önce bir dosya seçin.',fg=TOKENS['danger'])
            return
        self.busy=True
        self.app.ingest_busy=True
        self.choose_button.configure(state='disabled')
        self.start_button.configure(state='disabled')
        self.status_label.configure(text=f'İçe alınıyor: {len(self.paths)} dosya',fg=TOKENS['primary'])
        paths=self.paths
        svc=self.app.services.intake
        out=self.result_queue
        def job():
            for path in paths:
                try:
                    r=svc.import_document(path)
                    out.put(('success',f'{Path(path).name} — {r.operation} · v{r.revision} · SHA {r.sha256[:16]}…'))
                except (OSError, IntakeError, ValueError) as exc:
                    out.put(('failure',f'{Path(path).name} — {getattr(exc,"code","IO_ERROR")}: {exc}'))
                except Exception:
                    out.put(('failure',f'{Path(path).name} — Beklenmedik yerel içe alma hatası'))
            self.app.ingest_busy=False
            out.put(('done',''))
        threading.Thread(target=job,daemon=True,name='LK-Ingest-G03').start()
        self.after(100,self._poll)

    def _poll(self):
        if not self.winfo_exists():
            return
        done=False
        while True:
            try: mode,detail=self.result_queue.get_nowait()
            except queue.Empty: break
            if mode=='done':done=True
            else: self._log(('✓ ' if mode=='success' else '! ')+detail)
        if done:
            self.busy=False
            self.choose_button.configure(state='normal')
            self.start_button.configure(state='normal')
            self.status_label.configure(text='İçe alma tamamlandı. Sonuçları inceleyin.',fg=TOKENS['success'])
        else:
            self.after(100,self._poll)


def show_library(app):
    _section(app,'Yerel kütüphane · SHA-256 sürüm kaydı · henüz indekslenmedi')
    app.library_panel=LibraryPanel(app.content,app=app)
    app.library_panel.pack(fill='both',expand=True,padx=30,pady=(0,25))


def show_import(app):
    _section(app,'Kaynaklar yalnız yerel diskte saklanır · her belge ayrı doğrulanır')
    app.import_panel=ImportPanel(app.content,app=app)
    app.import_panel.pack(fill='both',expand=True,padx=30,pady=(0,25))


def show_history(app):
    _section(app,'Belge sürüm geçmişi · eski sürümler silinmez')
    selected=app.router.state.selected_document_id
    card=Card(app.content)
    card.pack(fill='x',padx=30)
    text(card.inner,'Belge Sürümleri',size=16,weight='bold').pack(anchor='w',pady=(0,12))
    if not selected:
        EmptyState(card.inner,'Belge seçilmedi','Kütüphane ekranında belge seçerek Sürümler düğmesine basın.').pack(fill='x')
        return
    rows=app.services.repository.versions(selected)
    for r in rows:
        line=tk.Frame(card.inner,bg=TOKENS['soft'],padx=10,pady=8)
        line.pack(fill='x',pady=3)
        text(line,f'v{r.revision}   ·   {r.sha256[:32]}…   ·   {_size(r.byte_size)}   ·   {r.added_at[:16]}',bg=TOKENS['soft'],size=10).pack(side='left')
        accessible_button(line,'SHA-256 Kontrol',lambda v=r:messagebox.showinfo('Bütünlük',
              'Özgün kayıt doğrulandı' if app.services.intake.verify(selected,v.revision) else 'UYARI: SHA-256 eşleşmiyor',parent=app)).pack(side='right')
    accessible_button(card.inner,'Kütüphaneye Dön',lambda:app.open_route(RouteId.LIBRARY)).pack(anchor='w',pady=(13,0))
