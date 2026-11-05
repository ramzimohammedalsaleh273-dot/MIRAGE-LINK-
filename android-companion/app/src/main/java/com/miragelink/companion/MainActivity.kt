package com.miragelink.companion

import android.app.Activity
import android.content.Intent
import android.media.projection.MediaProjectionManager
import android.os.Bundle
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView

class MainActivity : Activity() {
    private val requestCapture = 4107
    private lateinit var status: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(32, 48, 32, 32)
        }
        status = TextView(this).apply {
            textSize = 18f
            text = "MIRAGE LINK — تطبيق الهاتف المساعد\n\nشغّل نقطة اتصال هذا الهاتف، وصِل الكمبيوتر بها، ثم اضغط السماح بمشاركة الشاشة. بعد ذلك سيكتشف الكمبيوتر الهاتف تلقائياً عبر الشبكة المحلية."
        }
        val start = Button(this).apply {
            text = "السماح بعرض الشاشة"
            setOnClickListener {
                val manager = getSystemService(MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
                startActivityForResult(manager.createScreenCaptureIntent(), requestCapture)
            }
        }
        layout.addView(status)
        layout.addView(start)
        setContentView(layout)
    }

    @Deprecated("Deprecated by Android; retained for broad device compatibility")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == requestCapture) {
            if (resultCode == RESULT_OK && data != null) {
                val service = Intent(this, CaptureService::class.java).apply {
                    putExtra(CaptureService.EXTRA_RESULT_CODE, resultCode)
                    putExtra(CaptureService.EXTRA_RESULT_DATA, data)
                }
                startForegroundService(service)
                status.text = "تم السماح بمشاركة الشاشة. افتح MIRAGE LINK على الكمبيوتر واضغط «عرض عبر Wi-Fi». أبقِ هذا التطبيق مفتوحاً أثناء العرض."
            } else {
                status.text = "لم تمنح إذن مشاركة الشاشة."
            }
        }
    }
}
