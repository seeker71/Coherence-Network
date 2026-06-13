const downloads = [
  {
    target: "macOS arm64",
    artifact: "Native CLI tarball",
    href: "/downloads/hati-os/macos/arm64/hati-os-macos-arm64.tar.zst",
    checksum: "/downloads/hati-os/macos/arm64/hati-os-macos-arm64.tar.zst.sha256",
    proof: "Form-emitted C compiled to Mach-O arm64 and executed locally for fib, sum, and ack parity.",
  },
  {
    target: "Android arm64",
    artifact: "Native kernel package",
    href: "/downloads/hati-os/android/arm64/hati-os-android-arm64.tar.zst",
    checksum: "/downloads/hati-os/android/arm64/hati-os-android-arm64.tar.zst.sha256",
    proof: "Android ARM64 ELF executable and C-ABI shared library cross-compiled with local file and symbol proof.",
  },
  {
    target: "Android app",
    artifact: "Hati mesh sensing-organ APK",
    href: "/downloads/hati-os/android/arm64/coherence-sense-hati-mesh-debug.apk",
    checksum: "/downloads/hati-os/android/arm64/coherence-sense-hati-mesh-debug.apk.sha256",
    proof: "Debug APK builds locally, creates a stable organ id, announces to hati.mesh, polls organ/channel rows, and displays sensor flow rates.",
  },
];

export default function HatiOsPage() {
  return (
    <main className="min-h-screen bg-stone-50 text-stone-950">
      <section className="mx-auto flex w-full max-w-5xl flex-col gap-8 px-6 py-10 sm:py-14">
        <div className="space-y-3">
          <p className="text-sm font-medium uppercase tracking-wide text-emerald-700">
            Hati-OS native assets
          </p>
          <h1 className="text-4xl font-semibold tracking-normal sm:text-5xl">
            Hati-OS
          </h1>
          <p className="max-w-3xl text-base leading-7 text-stone-700">
            Public native packages for the Form fourth-kernel surface. Each
            download has a checksum and release receipt beside it.
          </p>
        </div>

        <div className="overflow-hidden rounded border border-stone-300 bg-white">
          <table className="w-full border-collapse text-left text-sm">
            <thead className="bg-stone-100 text-stone-700">
              <tr>
                <th className="px-4 py-3 font-semibold">Target</th>
                <th className="px-4 py-3 font-semibold">Artifact</th>
                <th className="px-4 py-3 font-semibold">Proof lane</th>
                <th className="px-4 py-3 font-semibold">Links</th>
              </tr>
            </thead>
            <tbody>
              {downloads.map((item) => (
                <tr key={item.target} className="border-t border-stone-200">
                  <td className="px-4 py-4 font-medium">{item.target}</td>
                  <td className="px-4 py-4">{item.artifact}</td>
                  <td className="px-4 py-4 text-stone-700">{item.proof}</td>
                  <td className="px-4 py-4">
                    <div className="flex flex-wrap gap-3">
                      <a className="font-medium text-emerald-800 underline" href={item.href}>
                        Download
                      </a>
                      <a className="font-medium text-emerald-800 underline" href={item.checksum}>
                        SHA256
                      </a>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <a
          className="w-fit font-medium text-emerald-800 underline"
          href="/downloads/hati-os/hati-os-public-assets-summary.json"
        >
          Release summary JSON
        </a>
      </section>
    </main>
  );
}
