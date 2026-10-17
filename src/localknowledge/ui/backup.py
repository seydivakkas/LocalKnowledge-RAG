"""G08 protected backup / restore screen. Filesystem work never runs on Tk event loop."""
from __future__ import annotations
import queue
import threading
import tkinter as tk
from tkinter import filedialog, simpledialog, ttk
from pathlib import Path

from .components import Card, text
from .theme import TOKENS
from ..storage.backup import BackupError


class BackupPanel(Card):
    def __init__(self,parent,app):
        super().__init__(parent)
        self.app=app
        self.mailbox=queue.Queue()
        self._timer=None
        self._busy=False
        text(self.inner,'Güvenli yerel yedekleme',size=15,weight='bold').pack(anchor='w',pady=(0,8))
        text(self.inner,'SQLite v3, FTS5 arama ve tüm belge sürümlerinin SHA-256 nesneleri korunur.',
             wrap=880,color=TOKENS['muted']).pack(anchor='w',pady=(0,16))
        bar=tk.Frame(self.inner,bg=TOKENS['card']);bar.pack(fill='x',pady=(0,10))
        self.buttons=[]
        for caption,method in [('Yeni Yedek Oluştur',self.create),('Yedeği Doğrula',self.inspect),
                               ('Yeni Konuma Geri Yükle',self.restore)]:
            button=ttk.Button(bar,text=caption,command=method)
            button.pack(side='left',padx=(0,10),ipady=6)
            self.buttons.append(button)
        self.status=text(self.inner,'Hazır — hiçbir yedek henüz oluşturulmadı.',color=TOKENS['muted'],wrap=900)
        self.status.pack(anchor='w',pady=(10,10))
        self.detail=tk.Text(self.inner,height=11,wrap='word',state='disabled',bd=0,
                            bg=TOKENS['soft'],fg=TOKENS['text'],font=('Segoe UI',10),padx=15,pady=12)
        self.detail.pack(fill='both',expand=True)
        self._show('Güvenlik sözleşmesi\n\n• Yedek klasörü yeni olmalıdır.\n• Belge kaynağı değiştirilmez.\n'
                   '• Geri yükleme mevcut veritabanının üzerine yapılmaz.\n'
                   '• Geri yüklenen veriyle çalışmak için uygulama yeni dizinden yeniden başlatılır.\n'
                   '• Eksik veya hash uyuşmayan yedek reddedilir.\n'
                   '• Gerçek Windows kullanıcı kabulü henüz yapılmadı.')
        self.bind('<Destroy>',self._cleanup,add='+')
        self._poll()

    def _show(self,value):
        self.detail.configure(state='normal')
        self.detail.delete('1.0','end')
        self.detail.insert('1.0',value)
        self.detail.configure(state='disabled')

    def _cleanup(self,event):
        if event.widget is self and self._timer is not None:
            try:self.after_cancel(self._timer)
            except tk.TclError:pass
            self._timer=None

    def _poll(self):
        if not self.winfo_exists():return
        try:
            while True:
                kind,result=self.mailbox.get_nowait()
                self._busy=False;self.app.backup_busy=False
                for button in self.buttons:button.configure(state='normal')
                if kind=='ok':
                    self.status.configure(text='İşlem tamamlandı — bütünlük kontrolü başarılı.')
                    self._show(f'Klasör: {result.destination}\nBelgeler: {result.document_count}\n'
                               f'Sürümler: {result.version_count}\nNesneler: {result.object_count}\n'
                               f'Doğrulanmış bayt: {result.total_bytes}\n'
                               f'Kaynak SQLite SHA-256: {result.source_digest}\n\n'
                               'Geri yükleme yapıldıysa uygulamanız hâlâ eski veri dizininde çalışır.')
                else:
                    code=getattr(result,'code','BACKUP_ERROR')
                    self.status.configure(text=f'İşlem reddedildi: {code}')
                    self._show(f'Hata kodu: {code}\n{result}\n\nÇalışan yerel veriler değiştirilmedi.')
        except queue.Empty:pass
        self._timer=self.after(100,self._poll)

    def _start(self,method,*args):
        if self._busy or self.app.backup_busy:return
        self._busy=True;self.app.backup_busy=True
        for button in self.buttons:button.configure(state='disabled')
        self.status.configure(text='Çevrimdışı dosya doğrulaması çalışıyor…')
        mailbox=self.mailbox
        def job():
            try:mailbox.put(('ok',method(*args)))
            except Exception as exc:mailbox.put(('error',exc))
        threading.Thread(target=job,daemon=True,name='LK-G08-Backup').start()

    @staticmethod
    def _target(parent,name):
        if not name or name in ('.','..') or '/' in name or '\\' in name or ':' in name or '\0' in name:
            raise BackupError('BAD_FOLDER_NAME','Yalnız yeni bir klasör adı giriniz.')
        return Path(parent)/name

    def create(self):
        if self._busy:return
        parent=filedialog.askdirectory(parent=self,title='Yeni yedeğin üst klasörünü seçin')
        if not parent:return
        name=simpledialog.askstring('Yeni yedek adı','Oluşturulacak yeni klasör adı:',
                                    initialvalue='LocalKnowledge-yedek',parent=self)
        if name is None:return
        try:target=self._target(parent,name)
        except BackupError as exc:self.status.configure(text=str(exc));return
        self._start(self.app.services.backup.create,target)

    def inspect(self):
        if self._busy:return
        source=filedialog.askdirectory(parent=self,title='Doğrulanacak yedek klasörünü seçin')
        if source:self._start(self.app.services.backup.inspect,source)

    def restore(self):
        if self._busy:return
        source=filedialog.askdirectory(parent=self,title='Yedek klasörünü seçin')
        if not source:return
        parent=filedialog.askdirectory(parent=self,title='Yeni veri klasörünün üst dizinini seçin')
        if not parent:return
        name=simpledialog.askstring('Yeni hedef dizin','Yeni ve daha önce kullanılmamış klasör adı:',
                                    initialvalue='LocalKnowledge-kurtarilan',parent=self)
        if name is None:return
        try:target=self._target(parent,name)
        except BackupError as exc:self.status.configure(text=str(exc));return
        self._start(self.app.services.backup.restore,source,target)


def show_backup(app):
    app._page_header('SHA-256 manifestolu kaynak, SQLite ve FTS5 yedekleme · G08')
    panel=BackupPanel(app.content,app)
    panel.pack(fill='both',expand=True,padx=30,pady=(0,20))
    app.backup_panel=panel
