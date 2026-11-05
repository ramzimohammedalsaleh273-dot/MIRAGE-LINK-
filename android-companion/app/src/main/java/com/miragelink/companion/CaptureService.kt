package com.miragelink.companion

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.MediaCodec
import android.media.MediaCodecInfo
import android.media.MediaFormat
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.IBinder
import android.util.DisplayMetrics
import android.view.WindowManager
import java.io.BufferedOutputStream
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.concurrent.thread

/**
 * User-consented Android screen capture. H.264 is sent over the local hotspot LAN.
 * TCP 27183 carries Annex-B AVC; UDP 27184 advertises the TCP endpoint.
 */
class CaptureService : Service() {
    companion object {
        const val EXTRA_RESULT_CODE = "projection_result_code"
        const val EXTRA_RESULT_DATA = "projection_result_data"
        private const val CHANNEL_ID = "mirage_capture"
        private const val NOTIFICATION_ID = 27183
        private const val VIDEO_PORT = 27183
        private const val DISCOVERY_PORT = 27184
        private const val MAGIC = "MIRAGE-LINK/1"
        private const val RESULT_CANCELED = 0
        private const val RESULT_OK = -1
    }

    private var projection: MediaProjection? = null
    private var virtualDisplay: VirtualDisplay? = null
    private var encoder: MediaCodec? = null
    private var server: ServerSocket? = null
    private var client: Socket? = null
    private val running = AtomicBoolean(false)
    private var width = 720
    private var height = 1280
    private var density = 1

    override fun onCreate() {
        super.onCreate()
        val manager = getSystemService(NotificationManager::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            manager.createNotificationChannel(
                NotificationChannel(CHANNEL_ID, "MIRAGE LINK", NotificationManager.IMPORTANCE_LOW)
            )
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val notification = Notification.Builder(this, CHANNEL_ID)
            .setContentTitle("MIRAGE LINK")
            .setContentText("مشاركة الشاشة المحلية جاهزة — بانتظار الكمبيوتر")
            .setSmallIcon(android.R.drawable.presence_video_online)
            .build()
        if (Build.VERSION.SDK_INT >= 29) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION)
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }

        val resultCode = intent?.getIntExtra(EXTRA_RESULT_CODE, RESULT_CANCELED) ?: RESULT_CANCELED
        val data = if (Build.VERSION.SDK_INT >= 33) {
            intent?.getParcelableExtra(EXTRA_RESULT_DATA, Intent::class.java)
        } else {
            @Suppress("DEPRECATION")
            intent?.getParcelableExtra(EXTRA_RESULT_DATA)
        }
        if (resultCode != RESULT_OK || data == null) {
            stopSelf()
            return START_NOT_STICKY
        }

        try {
            startNetwork()
            val manager = getSystemService(MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
            projection = manager.getMediaProjection(resultCode, data)
            projection?.registerCallback(object : MediaProjection.Callback() {
                override fun onStop() {
                    stopSelf()
                }
            }, null)
            startEncoder()
        } catch (e: Exception) {
            stopSelf()
        }
        return START_NOT_STICKY
    }

    private fun startNetwork() {
        running.set(true)
        server = ServerSocket(VIDEO_PORT, 1, InetAddress.getByName("0.0.0.0"))
        thread(name = "mirage-accept", isDaemon = true) {
            try {
                val accepted = server?.accept() ?: return@thread
                client = accepted
                accepted.tcpNoDelay = true
                streamEncoderTo(accepted)
            } catch (_: Exception) {
                // A client disconnect is handled by service cleanup.
            } finally {
                stopSelf()
            }
        }
        thread(name = "mirage-discovery", isDaemon = true) {
            while (running.get()) {
                try {
                    DatagramSocket().use { socket ->
                        socket.broadcast = true
                        val payload = "$MAGIC|$VIDEO_PORT".toByteArray(Charsets.UTF_8)
                        val packet = DatagramPacket(payload, payload.size, InetAddress.getByName("255.255.255.255"), DISCOVERY_PORT)
                        socket.send(packet)
                    }
                    Thread.sleep(1200)
                } catch (_: Exception) {
                    Thread.sleep(1500)
                }
            }
        }
    }

    private fun startEncoder() {
        val metrics = DisplayMetrics()
        @Suppress("DEPRECATION")
        (getSystemService(WINDOW_SERVICE) as WindowManager).defaultDisplay.getRealMetrics(metrics)
        width = (metrics.widthPixels / 2) * 2
        height = (metrics.heightPixels / 2) * 2
        density = metrics.densityDpi

        val format = MediaFormat.createVideoFormat(MediaFormat.MIMETYPE_VIDEO_AVC, width, height).apply {
            setInteger(MediaFormat.KEY_COLOR_FORMAT, MediaCodecInfo.COLOR_FormatSurface)
            setInteger(MediaFormat.KEY_BIT_RATE, 8_000_000)
            setInteger(MediaFormat.KEY_FRAME_RATE, 30)
            setInteger(MediaFormat.KEY_I_FRAME_INTERVAL, 1)
        }
        val codec = MediaCodec.createEncoderByType(MediaFormat.MIMETYPE_VIDEO_AVC)
        codec.configure(format, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE)
        val inputSurface = codec.createInputSurface()
        codec.start()
        encoder = codec
        virtualDisplay = projection?.createVirtualDisplay(
            "MIRAGE-LINK", width, height, density,
            DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
            inputSurface, null, null
        )
    }

    private fun streamEncoderTo(socket: Socket) {
        val codec = encoder ?: return
        val output = BufferedOutputStream(socket.getOutputStream(), 256 * 1024)
        val info = MediaCodec.BufferInfo()
        while (running.get() && !socket.isClosed) {
            val index = codec.dequeueOutputBuffer(info, 10_000)
            if (index >= 0) {
                val buffer = codec.getOutputBuffer(index)
                if (buffer != null && info.size > 0) {
                    buffer.position(info.offset)
                    buffer.limit(info.offset + info.size)
                    val bytes = ByteArray(info.size)
                    buffer.get(bytes)
                    output.write(bytes)
                    output.flush()
                }
                codec.releaseOutputBuffer(index, false)
            } else if (index == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                // Codec configuration (SPS/PPS) is emitted in subsequent output buffers.
            }
        }
    }

    override fun onDestroy() {
        running.set(false)
        try { client?.close() } catch (_: Exception) {}
        try { server?.close() } catch (_: Exception) {}
        try { virtualDisplay?.release() } catch (_: Exception) {}
        try { encoder?.stop() } catch (_: Exception) {}
        try { encoder?.release() } catch (_: Exception) {}
        try { projection?.stop() } catch (_: Exception) {}
        client = null
        server = null
        virtualDisplay = null
        encoder = null
        projection = null
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

}
