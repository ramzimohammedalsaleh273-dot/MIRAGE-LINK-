"""واجهة Windows عربية أولية لـ MIRAGE LINK."""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from .engine import Engine, MirageError

class MirageWindow:
    def __init__(self, root):
        self.root=root; self.engine=Engine(); self.process=None; self.device_map={}
        root.title("MIRAGE LINK — عرض شاشة الهاتف"); root.geometry("720x500"); root.minsize(650,450)
        root.protocol("WM_DELETE_WINDOW", self.close)
        style=ttk.Style()
        try: style.theme_use("vista")
        except tk.TclError: pass
        outer=ttk.Frame(root,padding=18); outer.pack(fill="both",expand=True)
        ttk.Label(outer,text="MIRAGE LINK",font=("Segoe UI",18,"bold")).pack(anchor="e")
        ttk.Label(outer,text="عرض شاشة Android عبر USB أو شبكة محلية دون إنترنت",justify="right").pack(anchor="e",pady=(4,14))
        dev=ttk.LabelFrame(outer,text="الهاتف والاتصال",padding=10); dev.pack(fill="x",pady=5)
        row=ttk.Frame(dev); row.pack(fill="x")
        ttk.Button(row,text="تحديث الأجهزة",command=self.refresh).pack(side="right")
        self.device=tk.StringVar()
        self.combo=ttk.Combobox(row,textvariable=self.device,state="readonly",justify="right")
        self.combo.pack(side="right",fill="x",expand=True,padx=8)
        ttk.Label(dev,text="الاتصال اللاسلكي: استخدم عنوان IP والمنفذ الظاهرين في إعدادات الهاتف.",justify="right").pack(anchor="e",pady=(10,4))
        net=ttk.Frame(dev); net.pack(fill="x")
        self.endpoint=tk.StringVar(); self.code=tk.StringVar()
        ttk.Entry(net,textvariable=self.endpoint,justify="right",width=22).pack(side="right",padx=4)
        ttk.Button(net,text="اتصال",command=self.connect).pack(side="right",padx=4)
        ttk.Entry(net,textvariable=self.code,justify="right",width=12).pack(side="right",padx=4)
        ttk.Button(net,text="اقتران",command=self.pair).pack(side="right",padx=4)
        q=ttk.LabelFrame(outer,text="جودة العرض",padding=10); q.pack(fill="x",pady=8)
        qr=ttk.Frame(q); qr.pack(fill="x")
        self.rate=tk.StringVar(value="40M"); self.fps=tk.StringVar(value="60")
        ttk.Label(qr,text="معدل نقل الفيديو").pack(side="right",padx=8)
        ttk.Combobox(qr,textvariable=self.rate,values=("16M","24M","40M"),state="readonly",width=9,justify="center").pack(side="right")
        ttk.Label(qr,text="أقصى إطارات/ثانية").pack(side="right",padx=(20,8))
        ttk.Combobox(qr,textvariable=self.fps,values=("30","60"),state="readonly",width=7,justify="center").pack(side="right")
        ttk.Label(q,text="الدقة الأصلية للهاتف 720 × 1640. معدل البت الأعلى يقلل الضغط ولا يصنع تفاصيل إضافية.",justify="right",wraplength=650).pack(anchor="e",pady=(9,0))
        actions=ttk.Frame(outer); actions.pack(fill="x",pady=12)
        ttk.Button(actions,text="إيقاف العرض",command=self.stop).pack(side="left")
        ttk.Button(actions,text="بدء عرض الشاشة",command=self.start).pack(side="right")
        self.status=tk.StringVar(value="جاهز — صِل الهاتف ووافق على تصحيح USB.")
        ttk.Label(outer,textvariable=self.status,wraplength=660,justify="right").pack(fill="x",anchor="e",pady=8)
        ttk.Label(outer,text="الألوان تتأثر أيضاً بمعايرة شاشة الكمبيوتر وملف الألوان وHDR؛ لا نضيف فلاتر عشوائية تغيّر ألوان الهاتف.",wraplength=660,justify="right").pack(anchor="e",pady=5)
        self.refresh()
    def refresh(self):
        try:
            ds=[d for d in self.engine.devices() if d.state=="device"]
            self.device_map={f"{d.serial} | {d.details}":d.serial for d in ds}
            self.combo["values"]=list(self.device_map)
            if ds: self.combo.current(0); self.status.set(f"تم العثور على {len(ds)} جهاز جاهز.")
            else: self.device.set(""); self.status.set("لا يوجد هاتف مصرح به. افحص الكابل وموافقة تصحيح USB.")
        except MirageError as e: self.status.set(str(e))
    def connect(self):
        try:
            r=self.engine.connect(self.endpoint.get().strip()); self.status.set(r or "تم طلب الاتصال؛ حدّث قائمة الأجهزة."); self.refresh()
        except MirageError as e: messagebox.showerror("تعذر الاتصال",str(e))
    def pair(self):
        try:
            r=self.engine.pair(self.endpoint.get().strip(),self.code.get().strip()); self.status.set(r or "تم طلب الاقتران. أكمل الاتصال بعنوان الاتصال.")
        except MirageError as e: messagebox.showerror("تعذر الاقتران",str(e))
    def start(self):
        if self.process and self.process.poll() is None: self.status.set("العرض يعمل بالفعل."); return
        serial=self.device_map.get(self.device.get())
        if not serial: messagebox.showwarning("اختر الهاتف","حدّد هاتفاً جاهزاً أولاً."); return
        try:
            self.process=self.engine.stream(serial=serial,codec="h264",max_fps=int(self.fps.get()),bit_rate=self.rate.get(),fullscreen=True)
            self.status.set(f"بدأ العرض للهاتف {serial}. نافذة scrcpy مستقلة ستظهر.")
            self.root.after(700,self.check_process)
        except MirageError as e: messagebox.showerror("تعذر بدء العرض",str(e))
    def check_process(self):
        if self.process is None: return
        code=self.process.poll()
        if code is None: self.root.after(700,self.check_process)
        else: self.status.set(f"انتهى العرض (رمز الخروج {code})."); self.process=None
    def stop(self):
        if self.process and self.process.poll() is None: self.process.terminate(); self.status.set("أُرسل أمر إيقاف العرض.")
        else: self.status.set("لا يوجد بث يعمل حالياً.")
    def close(self):
        if self.process and self.process.poll() is None: self.process.terminate()
        self.root.destroy()

def main():
    root=tk.Tk(); MirageWindow(root); root.mainloop()

if __name__=="__main__": main()
