"""G05 FTS5 search view and verified source-text preview (not a PDF viewer)."""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
import threading
import queue
from ..search.service import SearchError
from .routes import RouteId
from .components import Card, text
from .theme import TOKENS


class SearchPanel(tk.Frame):
    def __init__(self,parent,*,app):
        super().__init__(parent,bg=TOKENS['canvas'])
        self.app=app
        self.query=tk.StringVar(value=app.router.state.query)
        self.kind=tk.StringVar(value='ALL')
        self.created_from=tk.StringVar()
        self.hits={}
        self._events=queue.Queue()
        self._busy=False
        self._timer=None
        control=Card(self);control.pack(fill='x',pady=(0,14))
        row=tk.Frame(control.inner,bg=TOKENS['card']);row.pack(fill='x')
        text(row,'Belgede ara',size=10,weight='bold').pack(anchor='w')
        entry_row=tk.Frame(row,bg=TOKENS['card']);entry_row.pack(fill='x',pady=(6,8))
        self.entry=ttk.Entry(entry_row,textvariable=self.query,width=44)
        self.entry.pack(side='left',fill='x',expand=True,padx=(0,12),ipady=6)
        self.entry.bind('<Return>',lambda _e:self.run_search())
        self.button=ttk.Button(entry_row,text='Ara',command=self.run_search)
        self.button.pack(side='right')
        filters=tk.Frame(control.inner,bg=TOKENS['card']);filters.pack(fill='x')
        text(filters,'Tür',size=9).pack(side='left',padx=(0,6))
        self.kindbox=ttk.Combobox(filters,textvariable=self.kind,values=['ALL','PDF','DOCX','TXT'],width=9,state='readonly')
        self.kindbox.pack(side='left',padx=(0,18))
        text(filters,'Eklenme tarihi (YYYY-AA-GG) ve sonrası',size=9).pack(side='left',padx=(0,6))
        ttk.Entry(filters,textvariable=self.created_from,width=15).pack(side='left')
        self.status=text(self,'G04 metni tamamlanmış belgelerde yerel arama. BM25 bir güven yüzdesi değildir.',size=10,color=TOKENS['muted'],bg=TOKENS['canvas'])
        self.status.pack(anchor='w',pady=(0,12))
        shell=Card(self);shell.pack(fill='both',expand=True)
        self.table=ttk.Treeview(shell.inner,columns=('rank','name','kind','location','preview'),show='headings',height=11)
        for c,t,w in [('rank','#',40),('name','Belge',154),('kind','Tür',55),('location','Kaynak yeri',160),('preview','Özgün metin',268)]:
            self.table.heading(c,text=t);self.table.column(c,width=w,stretch=(c in ('name','preview')))
        self.table.pack(fill='both',expand=True)
        self.table.bind('<Double-1>',lambda _e:self.open_source())
        self.table.bind('<Return>',lambda _e:self.open_source())
        action=tk.Frame(shell.inner,bg=TOKENS['card']);action.pack(fill='x',pady=(9,0))
        ttk.Button(action,text='Kaynak Sayfasını Aç',command=self.open_source).pack(side='right')
        ttk.Button(action,text='Yalnız Metin',command=self.open_text_source).pack(side='right',padx=(0,8))
        text(action,'PDF: özgün sayfa; DOCX/TXT: doğrulanmış metin.',size=9,color=TOKENS['muted']).pack(side='left')
        self.bind('<Destroy>',self._on_destroy,add='+')
        self._poll()
        if self.query.get().strip():self.run_search()

    def _on_destroy(self,e):
        if e.widget is self and self._timer is not None:
            try:self.after_cancel(self._timer)
            except tk.TclError:pass
            self._timer=None

    def _poll(self):
        if not self.winfo_exists():return
        try:
            while True:
                result=self._events.get_nowait();self._busy=False;self.button.configure(state='normal')
                if isinstance(result,Exception):
                    self.status.configure(text=f'Arama yapılamadı: {result}',fg=TOKENS['muted'])
                else:self._render(result)
        except queue.Empty:pass
        self._timer=self.after(80,self._poll)

    def run_search(self):
        if self._busy:return
        query=self.query.get().strip()
        self.app.router.state.query=query
        if not query:
            self.status.configure(text='Aramak için en az bir sözcük girin.')
            return
        self._busy=True;self.button.configure(state='disabled');self.status.configure(text='Yerel dizinde aranıyor…')
        kind=self.kind.get();date=self.created_from.get().strip() or None
        engine=self.app.services.search
        mailbox=self._events
        def work():
            try:r=engine.search(query,kind=kind,created_from=date)
            except Exception as exc:
                r=exc if isinstance(exc,SearchError) else SearchError(type(exc).__name__)
            mailbox.put(r)
        threading.Thread(target=work,daemon=True,name='LK-G05-Query').start()

    def _render(self,results):
        self.hits={x.chunk_id:x for x in results}
        for i in self.table.get_children():self.table.delete(i)
        for hit in results:
            label=f'Sayfa {hit.unit_number+1}' if hit.kind=='PDF' else f'Paragraf {hit.unit_number+1}, {hit.char_start}–{hit.char_end}'
            snippet=' '.join(hit.exact_quote.split())[:145]
            self.table.insert('','end',iid=str(hit.chunk_id),values=(hit.rank,hit.name,hit.kind,label,snippet))
        self.status.configure(text=f'{len(results)} doğrulanmış sonuç · BM25 sırasıyla · yalnız güncel belge sürümleri' if results else 'Eşleşme bulunamadı. Metin çıkarma işlerinin tamamlanmasını kontrol edin.')

    def open_source(self):
        selected=self.table.selection()
        if not selected:return
        chunk_id=int(selected[0])
        if self.app.services.search.source_passage(chunk_id) is None:
            self.status.configure(text='Kaynak doğrulanamadı. Önizleme açılmadı.')
            return
        self.app.source_chunk_id=chunk_id
        self.app.source_query=self.query.get().strip()
        self.app.open_route(RouteId.SOURCE)

    def open_text_source(self):
        selected=self.table.selection()
        if not selected:return
        detail=self.app.services.search.source_passage(int(selected[0]))
        if detail is None:
            self.status.configure(text='Kaynak doğrulanamadı. Dosya değişmiş veya indeks eskimiş olabilir.')
            self.run_search();return
        hit,full,start,end=detail
        window=tk.Toplevel(self);window.title('Doğrulanmış Kaynak · LocalKnowledge')
        window.geometry('850x620');window.minsize(650,460)
        header=tk.Frame(window,padx=18,pady=14);header.pack(fill='x')
        tk.Label(header,text=hit.source_label,font=('Segoe UI',13,'bold'),anchor='w').pack(fill='x')
        tk.Label(header,text=f'Kaynak SHA-256: {hit.sha256}  ·  Doğrulama: başarılı',anchor='w',wraplength=780).pack(fill='x',pady=(5,0))
        tk.Label(header,text='G05 metin kanıtı; PDF özgün sayfası için Kaynak Sayfasını Aç seçeneğini kullanın.',anchor='w').pack(fill='x',pady=(5,0))
        wrap=tk.Frame(window,padx=14,pady=6);wrap.pack(fill='both',expand=True)
        viewer=tk.Text(wrap,wrap='word',font=('Segoe UI',11),padx=12,pady=12)
        scroll=ttk.Scrollbar(wrap,orient='vertical',command=viewer.yview)
        viewer.configure(yscrollcommand=scroll.set)
        viewer.pack(side='left',fill='both',expand=True);scroll.pack(side='right',fill='y')
        viewer.insert('1.0',full)
        viewer.tag_add('match',f'1.0+{start}c',f'1.0+{end}c')
        viewer.tag_configure('match',background='#fff0a8',foreground='#20334c')
        viewer.see(f'1.0+{start}c');viewer.configure(state='disabled')
        ttk.Button(window,text='Kapat',command=window.destroy).pack(anchor='e',padx=20,pady=12)


def show_search(app):
    app._page_header('Kaynaklı yerel belge araması · SQLite FTS5 + BM25 · G05')
    app.search_panel=SearchPanel(app.content,app=app)
    app.search_panel.pack(fill='both',expand=True,padx=30,pady=(0,20))
