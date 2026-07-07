package com.coherence.sema.mesh

// MeshTransport — the one socket every OS stack plugs into. The transports are NOT
// radios to build; Android already ships the stacks (NsdManager, WifiP2pManager,
// BluetoothSocket, AudioTrack/AudioRecord, camera+barcode, NfcAdapter). Each transport
// is a thin ADAPTER that wires one of those stacks to this interface, so the mesh speaks
// one frame and every medium carries it. See kernel observe/transport-ladder.fk (band 31)
// for the ranking + the honest floor: a transport is only "usable" once its adapter is
// wired AND its stack is reachable.

interface MeshTransport {
    val id: String          // matches the kernel ladder rung ("lan-mdns", "bluetooth", ...)
    val rank: Int           // lower = preferred (direct/local/offline-capable first)

    fun start()             // wire the stack up: advertise + begin serving/listening
    fun stop()
    fun reachable(): Boolean // is this stack actually carrying the mesh right now
}
