# تشغيل MIRAGE LINK من PowerShell — Windows

## 1) جلب المشروع
افتح PowerShell واكتب:

```powershell
cd "$env:USERPROFILE\Desktop"
git clone https://github.com/ramzimohammedalsaleh273-dot/MIRAGE-LINK-.git
cd "$env:USERPROFILE\Desktop\MIRAGE-LINK-"
```

إذا كان المجلد موجوداً مسبقاً:

```powershell
cd "$env:USERPROFILE\Desktop\MIRAGE-LINK-"
git pull origin main
```

## 2) تثبيت حزمة المشروع
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\تثبيت-MIRAGE-LINK.ps1"
```

## 3) فحص المتطلبات
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\تشغيل-MIRAGE-LINK.ps1" -Action doctor
```

يفترض أن يعثر السكربت تلقائياً على مجلد scrcpy المعروف:
`%USERPROFILE%\Desktop\scrcpy\scrcpy-win64-v3.3.1`
وإلا مرّر المسارات صراحة:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\تشغيل-MIRAGE-LINK.ps1" -Action doctor -AdbPath "C:\مسار\adb.exe" -ScrcpyPath "C:\مسار\scrcpy.exe"
```

## 4) فحص الهاتف ثم تشغيله
فعّل تصحيح USB في الهاتف، وصّل كابل بيانات، وافق على رسالة RSA، ثم:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\تشغيل-MIRAGE-LINK.ps1" -Action devices
powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\تشغيل-MIRAGE-LINK.ps1" -Action stream
```

## 5) الاختبارات
```powershell
py -m pip install -e ".[dev]"
py -m pytest
```

## تنبيه
لا يضم المستودع ملفات ADB أو scrcpy التنفيذية؛ يستخدم النسخ المثبتة محلياً، تجنباً لإعادة توزيع أدوات خارجية دون مراجعة تراخيصها. لا يحتاج البث المحلي إلى الإنترنت بعد تثبيت الأدوات.
