"""واجهة Windows عربية للتحكم في جودة بث MIRAGE LINK."""
from __future__ import annotations

import os
import subprocess
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox, simpledialog

from .engine import Engine, MirageError
from .wifi_receiver import WifiReceiver


QUALITY_PRESETS = {
    "فائق الوضوح (الموصى به)": ("h264", "40M", "60"),
    "سلاسة أعلى": ("h264", "24M", "60"),
    "تجربة HEVC (قد لا يدعمها الهاتف)": ("h265", "20M", "60"),
}


class MirageWindow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.engine = Engine()
        self.process = None
        self.fps_log_handle = None
        self.fps_log_path = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "MIRAGE LINK" / "logs" / "scrcpy-performance.log"
        self.device_map: dict[str, str] = {}
        self.wifi_receiver = None
        self.preview_window = None
        self.preview_label = None
        self.preview_photo = None

        root.title("MIRAGE LINK — عرض شاشة الهاتف")
        root.geometry("820x700")
        root.minsize(760, 650)
        root.protocol("WM_DELETE_WINDOW", self.close)

        style = ttk.Style()
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass

        outer = ttk.Frame(root, padding=18)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="MIRAGE LINK", font=("Segoe UI", 20, "bold")).pack(anchor="e")
        ttk.Label(
            outer,
            text="عرض شاشة Android عبر USB أو شبكة محلية دون إنترنت",
            justify="right",
        ).pack(anchor="e", pady=(4, 14))

        dev = ttk.LabelFrame(outer, text="اختر طريقة الاتصال", padding=10)
        dev.pack(fill="x", pady=5)

        usb = ttk.LabelFrame(dev, text="القسم الأول: الاتصال عبر USB", padding=8)
        usb.pack(fill="x", pady=(0, 8))
        usb_row = ttk.Frame(usb)
        usb_row.pack(fill="x")
        ttk.Label(usb_row, text="الأجهزة المتصلة بالكابل").pack(side="right", padx=5)
        self.device = tk.StringVar()
        self.combo = ttk.Combobox(usb_row, textvariable=self.device, state="readonly", justify="right")
        self.combo.pack(side="right", fill="x", expand=True, padx=8)
        ttk.Button(usb_row, text="تحديث أجهزة USB", command=self.refresh).pack(side="right")

        wifi = ttk.LabelFrame(dev, text="القسم الثاني: الاتصال عبر Wi-Fi فقط — لا يحتاج كابل USB", padding=8)
        wifi.pack(fill="x")
        ttk.Label(
            wifi,
            text=(
                "1) شغّل نقطة اتصال الهاتف، ثم صِل الكمبيوتر بها من زر اختيار شبكة Wi-Fi.\\n"
                "2) افتح تطبيق MIRAGE LINK المساعد على الهاتف واضغط السماح بعرض الشاشة.\\n"
                "3) اضغط «عرض عبر Wi-Fi» هنا؛ سيكتشف الهاتف تلقائياً ويبدأ العرض دون USB أو تصحيح لاسلكي."
            ),
            justify="right",
            wraplength=700,
        ).pack(anchor="e", pady=(0, 7))
        net = ttk.Frame(wifi)
        net.pack(fill="x")
        ttk.Button(net, text="اختيار شبكة Wi-Fi", command=self.select_wifi_network).pack(side="right", padx=3)
        ttk.Button(net, text="عرض عبر Wi-Fi", command=self.start_wifi).pack(side="left", padx=3)

        quality = ttk.LabelFrame(outer, text="أوضاع الجودة والأداء", padding=10)
        quality.pack(fill="x", pady=8)
        self.preset = tk.StringVar(value="فائق الوضوح (الموصى به)")
        preset_row = ttk.Frame(quality)
        preset_row.pack(fill="x")
        ttk.Label(preset_row, text="ملف الجودة").pack(side="right", padx=8)
        self.preset_combo = ttk.Combobox(
            preset_row, textvariable=self.preset, values=tuple(QUALITY_PRESETS),
            state="readonly", width=34, justify="right",
        )
        self.preset_combo.pack(side="right")
        self.preset_combo.bind("<<ComboboxSelected>>", self.apply_preset)

        controls = ttk.Frame(quality)
        controls.pack(fill="x", pady=(10, 0))
        self.rate = tk.StringVar(value="40M")
        self.fps = tk.StringVar(value="60")
        self.codec = tk.StringVar(value="h264")
        ttk.Label(controls, text="معدل نقل الفيديو").pack(side="right", padx=6)
        ttk.Combobox(
            controls, textvariable=self.rate, values=("16M", "24M", "40M"),
            state="readonly", width=8, justify="center",
        ).pack(side="right")
        ttk.Label(controls, text="أقصى إطارات/ث").pack(side="right", padx=(16, 6))
        ttk.Combobox(
            controls, textvariable=self.fps, values=("30", "60"),
            state="readonly", width=6, justify="center",
        ).pack(side="right")
        ttk.Label(controls, text="الترميز").pack(side="right", padx=(16, 6))
        ttk.Combobox(
            controls, textvariable=self.codec, values=("h264", "h265"),
            state="readonly", width=7, justify="center",
        ).pack(side="right")

        latency = ttk.Frame(quality)
        latency.pack(fill="x", pady=(10, 0))
        self.buffer_ms = tk.StringVar(value="0")
        self.show_fps = tk.BooleanVar(value=True)
        ttk.Label(latency, text="تعويض اهتزاز البث").pack(side="right", padx=6)
        ttk.Combobox(
            latency, textvariable=self.buffer_ms, values=("0", "25", "50"),
            state="readonly", width=7, justify="center",
        ).pack(side="right")
        ttk.Checkbutton(
            latency, text="إظهار قياس الإطارات الفعلي", variable=self.show_fps
        ).pack(side="right", padx=14)

        ttk.Label(
            quality,
            text=(
                "يُلتقط الهاتف بدقته الأصلية 720 × 1640 دون تصغير. "
                "40M يقلل آثار الضغط ولا يضيف تفاصيل أو يحوّل المصدر إلى 2K/4K. "
                "H.265 خيار تجريبي وقد لا يدعمه مرمّز الهاتف."
            ),
            justify="right",
            wraplength=710,
        ).pack(anchor="e", pady=(10, 0))

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=12)
        ttk.Button(actions, text="إيقاف العرض", command=self.stop).pack(side="left")
        ttk.Button(actions, text="بدء عرض الشاشة", command=self.start).pack(side="right")

        self.status = tk.StringVar(value="جاهز — اختر USB أو شغّل عرض Wi-Fi من تطبيق الهاتف المساعد.")
        ttk.Label(outer, textvariable=self.status, wraplength=710, justify="right").pack(
            fill="x", anchor="e", pady=8
        )
        ttk.Label(
            outer,
            text=(
                "ملاحظة: تكبير نافذة العرض لا يرفع الدقة الأصلية. "
                "تحسين الدقة بالذكاء الاصطناعي غير مفعّل بعد؛ سنختبره منفصلاً حتى لا يسبب تقطيعاً."
            ),
            wraplength=710,
            justify="right",
        ).pack(anchor="e", pady=5)
        self.refresh()

    def apply_preset(self, _event=None):
        codec, rate, fps = QUALITY_PRESETS[self.preset.get()]
        self.codec.set(codec)
        self.rate.set(rate)
        self.fps.set(fps)

    def refresh(self):
        try:
            devices = [d for d in self.engine.devices() if d.state == "device"]
            self.device_map = {f"{d.serial} | {d.details}": d.serial for d in devices}
            self.combo["values"] = list(self.device_map)
            if devices:
                self.combo.current(0)
                self.status.set(f"تم العثور على {len(devices)} جهاز جاهز.")
            else:
                self.device.set("")
                self.status.set("لا يوجد هاتف متصل حالياً. استخدم تحديث USB أو أكمل الاقتران والاتصال عبر Wi-Fi.")
        except MirageError as exc:
            self.status.set(str(exc))

    def select_wifi_network(self):
        """Open the native Windows network picker; the user selects any hotspot/router."""
        if os.name != "nt":
            messagebox.showinfo("اختيار الشبكة", "اختيار الشبكات من هذه الواجهة متاح في إصدار Windows.")
            return
        try:
            os.startfile("ms-availablenetworks:")
            self.status.set("اختر نقطة اتصال الهاتف من قائمة شبكات Windows، ثم ارجع واضغط «عرض عبر Wi-Fi».")
        except OSError as exc:
            messagebox.showerror("تعذر فتح الشبكات", str(exc))

    def start_wifi(self):
        """Listen for the Android companion beacon and show its H.264 stream."""
        if self.wifi_receiver is not None:
            self.status.set("البحث أو عرض Wi-Fi يعمل بالفعل.")
            return
        self._open_preview()
        self.wifi_receiver = WifiReceiver(
            on_frame=lambda image: self.root.after(0, self._show_frame, image),
            on_status=lambda message: self.root.after(0, self.status.set, message),
        )
        self.wifi_receiver.start()

    def _open_preview(self):
        if self.preview_window and self.preview_window.winfo_exists():
            self.preview_window.deiconify()
            return
        self.preview_window = tk.Toplevel(self.root)
        self.preview_window.title("MIRAGE LINK — عرض الهاتف عبر Wi-Fi")
        self.preview_window.geometry("900x650")
        self.preview_label = ttk.Label(self.preview_window, text="بانتظار الهاتف...")
        self.preview_label.pack(fill="both", expand=True, padx=8, pady=8)

    def _show_frame(self, image):
        if not self.preview_window or not self.preview_window.winfo_exists():
            return
        from PIL import ImageTk
        image.thumbnail((1600, 1100))
        self.preview_photo = ImageTk.PhotoImage(image)
        self.preview_label.configure(image=self.preview_photo, text="")

    def start(self):
        serial = self.device_map.get(self.device.get())
        if not serial:
            messagebox.showwarning("اختر هاتف USB", "حدّد هاتفاً جاهزاً في قسم USB أولاً.")
            return
        self._start_stream(serial)

    def _start_stream(self, serial):
        if self.process and self.process.poll() is None:
            self.status.set("العرض يعمل بالفعل.")
            return
        log_handle = None
        try:
            if self.show_fps.get():
                self.fps_log_path.parent.mkdir(parents=True, exist_ok=True)
                log_handle = self.fps_log_path.open("a", encoding="utf-8")
            self.process = self.engine.stream(
                serial=serial,
                codec=self.codec.get(),
                max_fps=int(self.fps.get()),
                bit_rate=self.rate.get(),
                fullscreen=True,
                video_buffer_ms=int(self.buffer_ms.get()),
                print_fps=self.show_fps.get(),
                stdout=log_handle,
                stderr=subprocess.STDOUT if log_handle else None,
            )
            self.fps_log_handle = log_handle
            self.status.set(
                f"بدأ العرض: {serial} — {self.codec.get()} — "
                f"{self.rate.get()} — حتى {self.fps.get()} إطار/ث — "
                f"مخزن {self.buffer_ms.get()}ms."
                + (f" سجل قياس الأداء: {self.fps_log_path}" if log_handle else "")
            )
            self.root.after(700, self.check_process)
        except (MirageError, OSError) as exc:
            if log_handle:
                log_handle.close()
            messagebox.showerror("تعذر بدء العرض", str(exc))

    def check_process(self):
        if self.process is None:
            return
        code = self.process.poll()
        if code is None:
            self.root.after(700, self.check_process)
        else:
            self.status.set(f"انتهى العرض (رمز الخروج {code}).")
            self.process = None
            if self.fps_log_handle:
                self.fps_log_handle.close()
                self.fps_log_handle = None

    def stop(self):
        if self.wifi_receiver is not None:
            self.wifi_receiver.stop()
            self.wifi_receiver = None
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.status.set("أُرسل أمر إيقاف العرض.")
        else:
            self.status.set("لا يوجد بث يعمل حالياً.")

    def close(self):
        if self.wifi_receiver is not None:
            self.wifi_receiver.stop()
            self.wifi_receiver = None
        if self.process and self.process.poll() is None:
            self.process.terminate()
        if self.fps_log_handle:
            self.fps_log_handle.close()
            self.fps_log_handle = None
        self.root.destroy()


def main():
    root = tk.Tk()
    MirageWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
