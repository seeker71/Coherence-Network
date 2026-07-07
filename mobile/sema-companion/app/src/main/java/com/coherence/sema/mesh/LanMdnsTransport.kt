package com.coherence.sema.mesh

// LanMdnsTransport — the first stack wired to a real second transport (rank 7). No radio
// built: this is Android's own NsdManager (mDNS/DNS-SD) + a plain TCP ServerSocket. The
// phone advertises `_sema-mesh._tcp`, and any organ on the same network discovers it and
// reads a presence frame — the mesh reaching a peer directly, no cloud proxy in the path.
//
// Provable from any Mac on the same wifi:
//   dns-sd -B _sema-mesh._tcp                       # the phone appears
//   dns-sd -L "sema-<id>" _sema-mesh._tcp           # its host + port
//   nc <phone-ip> <port>                            # reads: sema-mesh|<organ>|<v>
//
// Scope wired tonight: advertise + serve the presence frame (proven). Full duplex mesh-op
// parity over LAN is the next increment — the socket and discovery are the hard part and
// they are done; the rest is framing more verbs onto the same wire.

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import com.coherence.sema.core.DeviceIdentity
import java.net.ServerSocket
import kotlin.concurrent.thread

class LanMdnsTransport(
    private val context: Context,
    private val versionCode: Int,
) : MeshTransport {

    override val id = "lan-mdns"
    override val rank = 7

    private val serviceType = "_sema-mesh._tcp"
    private var server: ServerSocket? = null
    private var nsd: NsdManager? = null
    private var regListener: NsdManager.RegistrationListener? = null
    private var accept: Thread? = null
    @Volatile private var advertising = false

    override fun start() {
        if (server != null) return
        val organ = DeviceIdentity.organId(context)
        val sock = try { ServerSocket(0) } catch (e: Exception) { return }  // ephemeral port
        server = sock

        accept = thread(name = "sema-lan-mesh", isDaemon = true) {
            val frame = "sema-mesh|$organ|$versionCode\n".toByteArray()
            while (!sock.isClosed) {
                try {
                    sock.accept().use { peer ->
                        peer.getOutputStream().apply { write(frame); flush() }
                    }
                } catch (e: Exception) { if (sock.isClosed) break }
            }
        }

        val info = NsdServiceInfo().apply {
            serviceName = "sema-$organ"
            this.serviceType = this@LanMdnsTransport.serviceType
            port = sock.localPort
        }
        val mgr = context.getSystemService(Context.NSD_SERVICE) as NsdManager
        nsd = mgr
        regListener = object : NsdManager.RegistrationListener {
            override fun onServiceRegistered(s: NsdServiceInfo) { advertising = true }
            override fun onRegistrationFailed(s: NsdServiceInfo, err: Int) { advertising = false }
            override fun onServiceUnregistered(s: NsdServiceInfo) { advertising = false }
            override fun onUnregistrationFailed(s: NsdServiceInfo, err: Int) {}
        }
        try {
            mgr.registerService(info, NsdManager.PROTOCOL_DNS_SD, regListener)
        } catch (e: Exception) { advertising = false }
    }

    override fun stop() {
        try { regListener?.let { nsd?.unregisterService(it) } } catch (e: Exception) {}
        try { server?.close() } catch (e: Exception) {}
        server = null; advertising = false
    }

    override fun reachable(): Boolean = advertising && server?.isClosed == false
}
