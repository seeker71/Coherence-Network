import Foundation
import Darwin

// This Mac's own body, read natively from Darwin — no shell, no web. CPU, RAM, disk,
// network live; GPU is honestly pending (needs IOKit/private APIs) and is marked so.

@MainActor
final class ResourceModel: ObservableObject {
    @Published var cpuPercent: Double = 0
    @Published var ramUsedGB: Double = 0
    @Published var ramTotalGB: Double = 0
    @Published var ramPercent: Double = 0
    @Published var diskPercent: Double = 0
    @Published var netRxKBs: Double = 0
    @Published var netTxKBs: Double = 0

    private var prevCPU: (busy: Double, total: Double)? = nil
    private var prevNet: (rx: UInt64, tx: UInt64, t: Date)? = nil

    func start() { Task { await loop() } }

    private func loop() async {
        while !Task.isCancelled {
            sample()
            try? await Task.sleep(nanoseconds: 2_000_000_000)
        }
    }

    func sample() {
        cpuPercent = cpuUsage()
        let (usedGB, totalGB, pct) = ramUsage()
        ramUsedGB = usedGB; ramTotalGB = totalGB; ramPercent = pct
        diskPercent = diskUsage()
        let (rx, tx) = netRates()
        netRxKBs = rx; netTxKBs = tx
    }

    private func cpuUsage() -> Double {
        var load = host_cpu_load_info()
        var count = mach_msg_type_number_t(MemoryLayout<host_cpu_load_info>.stride / MemoryLayout<integer_t>.stride)
        let kr = withUnsafeMutablePointer(to: &load) { ptr in
            ptr.withMemoryRebound(to: integer_t.self, capacity: Int(count)) {
                host_statistics(mach_host_self(), HOST_CPU_LOAD_INFO, $0, &count)
            }
        }
        guard kr == KERN_SUCCESS else { return cpuPercent }
        let user = Double(load.cpu_ticks.0)
        let sys = Double(load.cpu_ticks.1)
        let idle = Double(load.cpu_ticks.2)
        let nice = Double(load.cpu_ticks.3)
        let busy = user + sys + nice
        let total = busy + idle
        defer { prevCPU = (busy, total) }
        guard let p = prevCPU else { return 0 }
        let db = busy - p.busy, dt = total - p.total
        return dt > 0 ? min(100, max(0, db / dt * 100)) : 0
    }

    private func ramUsage() -> (Double, Double, Double) {
        let total = Double(ProcessInfo.processInfo.physicalMemory)
        var stats = vm_statistics64()
        var count = mach_msg_type_number_t(MemoryLayout<vm_statistics64>.stride / MemoryLayout<integer_t>.stride)
        let kr = withUnsafeMutablePointer(to: &stats) { ptr in
            ptr.withMemoryRebound(to: integer_t.self, capacity: Int(count)) {
                host_statistics64(mach_host_self(), HOST_VM_INFO64, $0, &count)
            }
        }
        let g = 1_073_741_824.0
        guard kr == KERN_SUCCESS else { return (0, total / g, 0) }
        let page = Double(vm_page_size)
        let used = (Double(stats.active_count) + Double(stats.wire_count) + Double(stats.compressor_page_count)) * page
        return (used / g, total / g, total > 0 ? used / total * 100 : 0)
    }

    private func diskUsage() -> Double {
        if let v = try? URL(fileURLWithPath: "/").resourceValues(forKeys: [.volumeAvailableCapacityKey, .volumeTotalCapacityKey]),
           let avail = v.volumeAvailableCapacity, let tot = v.volumeTotalCapacity, tot > 0 {
            return Double(tot - avail) / Double(tot) * 100
        }
        return diskPercent
    }

    private func netRates() -> (Double, Double) {
        var rx: UInt64 = 0, tx: UInt64 = 0
        var ifaddr: UnsafeMutablePointer<ifaddrs>?
        if getifaddrs(&ifaddr) == 0 {
            var ptr = ifaddr
            while let cur = ptr {
                let f = cur.pointee
                if f.ifa_addr?.pointee.sa_family == UInt8(AF_LINK), let raw = f.ifa_data {
                    let name = String(cString: f.ifa_name)
                    if name.hasPrefix("en") || name.hasPrefix("pdp_ip") {
                        let d = raw.assumingMemoryBound(to: if_data.self).pointee
                        rx += UInt64(d.ifi_ibytes); tx += UInt64(d.ifi_obytes)
                    }
                }
                ptr = f.ifa_next
            }
            freeifaddrs(ifaddr)
        }
        let now = Date()
        defer { prevNet = (rx, tx, now) }
        guard let p = prevNet else { return (0, 0) }
        let dt = now.timeIntervalSince(p.t)
        if dt <= 0 { return (netRxKBs, netTxKBs) }
        return (max(0, Double(rx &- p.rx) / dt / 1024), max(0, Double(tx &- p.tx) / dt / 1024))
    }
}
