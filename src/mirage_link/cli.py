"""Arabic command-line interface."""
from __future__ import annotations
import argparse
import sys
from .engine import Engine, MirageError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mirage", description="MIRAGE LINK — محرك اتصال وبث شاشة Android")
    parser.add_argument("--adb", help="المسار الكامل لملف adb")
    parser.add_argument("--scrcpy", help="المسار الكامل لملف scrcpy")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="فحص الأدوات والاتصال")
    sub.add_parser("devices", help="عرض الأجهزة")
    p = sub.add_parser("pair", help="اقتران لاسلكي")
    p.add_argument("endpoint"); p.add_argument("code")
    c = sub.add_parser("connect", help="الاتصال بعنوان IP ومنفذ")
    c.add_argument("endpoint")
    t = sub.add_parser("tcpip", help="تفعيل ADB TCP/IP بعد توصيل USB")
    t.add_argument("port", nargs="?", type=int, default=5555)
    t.add_argument("--serial")
    s = sub.add_parser("stream", help="بدء بث الشاشة بجودتها الأصلية ومعدل بت مرتفع")
    s.add_argument("--serial")
    s.add_argument("--codec", choices=["auto", "h264", "h265"], default="h264")
    s.add_argument("--max-fps", type=int, default=60)
    s.add_argument("--bit-rate", default="40M")
    s.add_argument("--fullscreen", action="store_true")
    s.add_argument("--max-size", type=int,
                   help="اختياري فقط: يقيّد حجم الالتقاط؛ اتركه فارغاً للحفاظ على الدقة الأصلية")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    engine = Engine(args.adb, args.scrcpy)
    try:
        if args.command == "doctor":
            print("=== تشخيص MIRAGE LINK ===")
            for key, value in engine.doctor().items():
                print(f"{key}: {value}")
        elif args.command == "devices":
            devices = engine.devices()
            if not devices:
                print("لم يتم العثور على أجهزة. افحص التصحيح والكابل أو الاتصال اللاسلكي.")
            for device in devices:
                print(f"{device.serial}\t{device.state}\t{device.details}")
        elif args.command == "pair":
            print(engine.pair(args.endpoint, args.code))
        elif args.command == "connect":
            print(engine.connect(args.endpoint))
        elif args.command == "tcpip":
            print(engine.tcpip(args.port, args.serial))
        elif args.command == "stream":
            devices = engine.devices()
            serial = args.serial
            if not serial:
                ready = [d for d in devices if d.state == "device"]
                if not ready:
                    raise MirageError("لا يوجد هاتف مصرح به. نفّذ mirage devices وافق على رسالة التصحيح في الهاتف.")
                if len(ready) > 1:
                    raise MirageError("هناك عدة أجهزة. حدّد الجهاز باستخدام --serial SERIAL.")
                serial = ready[0].serial
            print(f"بدء البث للجهاز: {serial}")
            print("ملف الجودة: طبيعي مرتفع — دقة المصدر الأصلية دون تصغير — 40M — حتى 60 إطاراً/ثانية")
            process = engine.stream(serial, args.codec, args.max_fps, args.bit_rate,
                                    args.fullscreen, args.max_size)
            print(f"تم تشغيل scrcpy (PID: {process.pid}). أغلق نافذة العرض لإنهاء البث.")
            return process.wait()
        return 0
    except MirageError as exc:
        print(f"خطأ: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
