// ════════════════════════════════════════════════════════════════════
// MASCHINELL ÜBERSETZT · machine-translated string fields from en.tsx
// JSX bodies remain in English; refinement welcome.
// To regenerate: python3 scripts/generate_curated_translations.py \
//                  --slug qualcomm-hdmi-hdcp --target-lang id --overwrite
// ════════════════════════════════════════════════════════════════════
import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {title: "Qualcomm Linux Kernel HDMI / HDCP - hard-encrypted tampilkan keluaran",description: "Sementara di Qualcomm, berkontribusi sebuah modul Linux kernel yang mendukung keluaran HDMI dengan enkripsi perangkat keras HDCP untuk MSM-family Soc. Tangga kunci HDCP, mesin cipher, mesin cable-state, dan pipa DRM / KMS - semua didorong dari modul kernel yang muncul jalur tampilan aman ke ruang service. Referensi langsung upstream dalam riwayat kernel git Linux.",
  },breadcrumbName: "Qualcomm",
  hero: {
    background:
      "linear-gradient(135deg, hsl(220 30% 8%), hsl(40 30% 14%) 50%, hsl(280 30% 16%))",
    overlayClass:
      "absolute inset-0 bg-gradient-to-t from-background via-background/85 to-background/30",eyebrow: "Bekerja",
    eyebrowClass: "text-[hsl(var(--chart-2))]",name: "Qualcomm - Linux HDMI / HDCP kernel modul",
    welcome: (
      <p>
        While at Qualcomm, contributed a Linux kernel module
        supporting <strong>HDMI output with hardware encryption</strong>
        {" "}for MSM-family SoCs. HDMI carries the visible signal;{" "}
        <Link href="https://en.wikipedia.org/wiki/High-bandwidth_Digital_Content_Protection" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
          HDCP
        </Link>
        {" "}— High-bandwidth Digital Content Protection — encrypts it
        in hardware so a downstream display can prove it is licensed
        to receive it. The driver glues the chip's cipher engine, key
        ladder, cable-state machine, and the upstream DRM/KMS surface
        into one kernel module that exposes the secure display path
        to userspace cleanly. References live upstream in the Linux
        kernel git history with the contributor's name on them.
      </p>
    ),
  },
  facts: [
    {label: "Era",value: "Dalam masa jabatan Qualcomm" },
    {label: "Substrat",value: "Kernel Linux" },
    {label: "Tampilkan protokol",
      value: (
        <>
          <Link href="https://en.wikipedia.org/wiki/HDMI" target="_blank" rel="noopener noreferrer" className="hover:text-primary">HDMI</Link>
          {" "}— High-Definition Multimedia Interface · TMDS lanes ·
          E-DDC for sink discovery · CEC for control
        </>
      ),
    },
    {label: "Undo-type",
      value: (
        <>
          <Link href="https://en.wikipedia.org/wiki/High-bandwidth_Digital_Content_Protection" target="_blank" rel="noopener noreferrer" className="hover:text-primary">HDCP</Link>
          {" "}— hardware key ladder · authentication-with-revocation ·
          link-integrity verification · cipher engine driving the TMDS
          lanes
        </>
      ),
    },
    {label: "Upstream",
      value: (
        <>
          References in the Linux kernel git history with the
          contributor's name. Find them by searching the kernel tree
          for{" "}
          <code className="text-foreground/80">git log --author="Urs Muff"</code>
          {" "}— see the{" "}
          <Link href="https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/" target="_blank" rel="noopener noreferrer" className="hover:text-primary">
            mainline tree
          </Link>
          {" "}and the{" "}
          <Link href="https://lore.kernel.org/" target="_blank" rel="noopener noreferrer" className="hover:text-primary">
            kernel mailing-list archive
          </Link>
          .
        </>
      ),
    },
    {label: "Garis Keturunan kedepan",
      value: (
        <>
          The Linux kernel's discipline — every commit signed off,
          every patch reviewed publicly, every change addressable by
          a hash — is the same discipline now expressed in the{" "}
          <Link href="/people/coherence-network" className="hover:text-primary">
            Coherence Network
          </Link>
          's commit verbs (<code className="text-foreground/80">tend</code> /
          <code className="text-foreground/80">attune</code> /
          <code className="text-foreground/80">compost</code> /
          <code className="text-foreground/80">release</code>).
          Different naming, same posture.
        </>
      ),
    },
  ],
  noteFromBody: {eyebrow: "Mengapa pekerjaan ini penting dalam tubuh bukti",
    body: (
      <p>
        The kernel work is the only piece in the body of evidence
        with a <em>public, attributed, immutable</em> trace. Quark
        and MindTouch and Trimble source code lives behind corporate
        walls; the BML thesis archive is local to this repo. But
        Linux kernel commits are signed-off by author, reviewed in
        public on the kernel mailing list, and merged into a tree
        that is mirrored across thousands of machines worldwide. A
        contribution to that tree carries the engineer's name into
        a corner of the commons that won't be edited away.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",heading: "Apa HDMI + HDCP sebenarnya membutuhkan dari driver kernel",
      body: (
        <>
          <p>
            HDMI looks simple from a userspace perspective: plug in
            a cable, the screen lights up. From the kernel's
            perspective, the path from a frame in memory to pixels on
            a remote display crosses{" "}
            <strong>five separate hardware blocks</strong>, each with
            its own clock domain, its own register set, and its own
            failure mode. The driver is what coordinates them.
          </p>
          <figure className="my-6 rounded-xl border border-border/40 bg-card/30 p-5">
            <svg viewBox="0 0 720 320" className="w-full h-auto" role="img" aria-labelledby="qc-hdmi-arch-title">
              <title id="qc-hdmi-arch-title">Qualcomm MSM HDMI/HDCP driver architecture</title>
              <g fontFamily="ui-sans-serif,system-ui" fontSize="12">
                {/* Top: userspace */}
                <rect x="60" y="20" width="600" height="40" rx="8" fill="hsl(220 25% 18%)" stroke="hsl(195 60% 60%)" />
                <text x="80" y="42" fill="hsl(195 80% 80%)" fontSize="13">Userspace · DRM/KMS clients</text>
                <text x="80" y="56" fill="hsl(195 50% 70%)" fontSize="10">SurfaceFlinger · Wayland · X11 · libdrm</text>

                <line x1="360" y1="60" x2="360" y2="76" stroke="hsl(220 30% 60%)" strokeWidth="1.2" />

                {/* DRM core */}
                <rect x="60" y="76" width="600" height="32" rx="6" fill="hsl(220 25% 16%)" stroke="hsl(280 60% 65%)" />
                <text x="80" y="96" fill="hsl(280 80% 82%)" fontSize="12">Linux DRM/KMS core · connector / encoder / CRTC objects</text>

                <line x1="360" y1="108" x2="360" y2="124" stroke="hsl(220 30% 60%)" strokeWidth="1.2" />

                {/* Driver layer */}
                <rect x="60" y="124" width="600" height="100" rx="10" fill="hsl(40 35% 16%)" stroke="hsl(40 80% 60%)" strokeWidth="2" />
                <text x="80" y="148" fill="hsl(40 90% 85%)" fontSize="14" fontWeight="500">Qualcomm MSM HDMI driver · the kernel module</text>
                <text x="80" y="166" fill="hsl(40 60% 75%)" fontSize="10">connector — hotplug · EDID parse · mode list · cable state</text>
                <text x="80" y="180" fill="hsl(40 60% 75%)" fontSize="10">encoder — TMDS encoding · audio / InfoFrame insertion</text>
                <text x="80" y="194" fill="hsl(40 60% 75%)" fontSize="10">HDCP state machine — auth · key ladder · link-integrity poll</text>
                <text x="80" y="208" fill="hsl(40 60% 75%)" fontSize="10">PHY config · TMDS clocks · power / clock domain transitions</text>

                <line x1="180" y1="224" x2="180" y2="244" stroke="hsl(220 30% 60%)" strokeWidth="1.2" />
                <line x1="360" y1="224" x2="360" y2="244" stroke="hsl(220 30% 60%)" strokeWidth="1.2" />
                <line x1="540" y1="224" x2="540" y2="244" stroke="hsl(220 30% 60%)" strokeWidth="1.2" />

                {/* Hardware blocks */}
                <g>
                  <rect x="60" y="244" width="180" height="56" rx="8" fill="hsl(220 25% 14%)" stroke="hsl(140 60% 55%)" />
                  <text x="150" y="266" textAnchor="middle" fill="hsl(140 80% 80%)" fontSize="11">HDMI controller</text>
                  <text x="150" y="282" textAnchor="middle" fill="hsl(140 50% 70%)" fontSize="9">TMDS encoder · audio</text>
                  <text x="150" y="294" textAnchor="middle" fill="hsl(140 50% 70%)" fontSize="9">CEC · DDC bus</text>
                </g>
                <g>
                  <rect x="270" y="244" width="180" height="56" rx="8" fill="hsl(220 25% 14%)" stroke="hsl(0 60% 60%)" />
                  <text x="360" y="266" textAnchor="middle" fill="hsl(0 70% 80%)" fontSize="11">HDCP cipher engine</text>
                  <text x="360" y="282" textAnchor="middle" fill="hsl(0 50% 70%)" fontSize="9">key ladder · auth</text>
                  <text x="360" y="294" textAnchor="middle" fill="hsl(0 50% 70%)" fontSize="9">in-line scrambling</text>
                </g>
                <g>
                  <rect x="480" y="244" width="180" height="56" rx="8" fill="hsl(220 25% 14%)" stroke="hsl(195 55% 60%)" />
                  <text x="570" y="266" textAnchor="middle" fill="hsl(195 80% 82%)" fontSize="11">PHY / clocks</text>
                  <text x="570" y="282" textAnchor="middle" fill="hsl(195 50% 75%)" fontSize="9">PLL · TMDS lanes</text>
                  <text x="570" y="294" textAnchor="middle" fill="hsl(195 50% 75%)" fontSize="9">power domain</text>
                </g>
              </g>
            </svg>
            <figcaption className="text-xs text-muted-foreground mt-3 text-center">
              Five layers from userspace to pins. The kernel module
              is the load-bearing middle — it presents a clean
              DRM/KMS surface upward and coordinates the HDMI
              controller, the HDCP cipher engine, and the PHY/clock
              domains downward.
            </figcaption>
          </figure>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "warm",eyebrow: "Apa yang sebenarnya HDCP lakukan",heading: "Enkripsi perangkat keras pada link yang bergerak",
      body: (
        <>
          <p>
            <Link href="https://en.wikipedia.org/wiki/High-bandwidth_Digital_Content_Protection" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
              HDCP
            </Link>
            {" "}is a key-ladder authentication protocol with in-line
            stream encryption. The first second of the link is spent
            in <em>authentication</em>: source and sink exchange
            public values, derive a shared session key from a key
            ladder rooted in device-specific secrets, and prove to
            each other that neither has been revoked. Once
            authenticated, the cipher engine in hardware uses the
            session key to scramble every TMDS pixel before it goes
            on the cable. The sink unscrambles in hardware on the
            other end. From the application's perspective the picture
            looks identical; what changed is that an unauthorised
            recorder on the cable can't reconstruct the frames.
          </p>
          <p>
            The driver's job in this is delicate. The cipher engine
            is fast but the link-integrity verification — the periodic
            check that the same key is still in effect at both ends —
            has to fire at very specific points in the video frame. A
            late check kills the picture (the sink falls back to a
            blank screen with "encryption error"); a missed check
            opens an audit hole. The kernel module times these
            actions against the video clock, kicks the hardware,
            collects the verification result, and either continues
            silently or tears the link down and re-authenticates. All
            without dropping frames userspace can see.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",heading: "Mengapa ini adalah satu-satunya public-atsatwork",
      body: (
        <>
          <p>
            Most of this body's work lives behind corporate walls.
            QuarkXPress source is internal. MindTouch source is
            internal. Trimble source is internal. The Qualcomm test
            harness ran on internal infrastructure. Even the BML
            thesis archive lives on a personal machine. None of that
            work has a public, attributed, immutable record outside
            the company that owned it.
          </p>
          <p>
            The Linux kernel is different. Every commit is{" "}
            <code className="text-foreground/80">Signed-off-by:</code>
            {" "}its author. Every change is reviewed publicly on the
            kernel mailing list, archived at{" "}
            <Link href="https://lore.kernel.org/" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
              lore.kernel.org
            </Link>
            , and merged into a tree mirrored to every machine that
            runs Linux. A contribution to that tree is forever-
            attributed to its author in a way no corporate codebase
            can match. To find this body's contributions, run{" "}
            <code className="text-foreground/80">git log --author="Urs Muff"</code>
            {" "}in any Linux kernel checkout — the patches surface
            with their full description, their date, their hash, and
            the file paths they touched.
          </p>
          <p>
            That's why this page lives differently than the others.
            The lived memory and architectural shape are here as
            framing; the <em>truth</em> is in the kernel git log,
            available to anyone. This network's curated text is a
            doorway; the kernel's own history is the source.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "cool",eyebrow: "Lapisan lima memikirkan permukaan lagi",heading: "Postur yang sama seperti Schindler",
      body: (
        <p>
          The driver's architecture — userspace → DRM/KMS core →
          kernel module → HDMI / HDCP / PHY hardware — is the same
          five-layer pattern this body first internalised in the{" "}
          <Link href="/people/c64-midi-interface" className="text-primary hover:underline">
            Commodore 64 MIDI work (age 13)
          </Link>
          {" "}(BASIC → ring buffer → assembly ISR → CIA chip → wire),
          ratified in the{" "}
          <Link href="/people/schindler-hc11-protocol" className="text-primary hover:underline">
            Schindler 7-layer ISO/OSI work
          </Link>
          , re-applied at the Trimble{" "}
          <Link href="/people/trimble-glue-layer" className="text-primary hover:underline">
            client/server glue layer
          </Link>
          , and now expressed at network scale in the{" "}
          <Link href="/people/coherence-network" className="text-primary hover:underline">
            Coherence Network
          </Link>
          's five-tier architecture. Each layer authoring against
          its own job; each layer addressable; clean contracts in
          between. Forty years; one shape.
        </p>
      ),
    },
  ],
  footer: (
    <p>
      Public attribution lives in the Linux kernel git history. To
      surface this body's commits, clone the kernel tree (
      <Link href="https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
        torvalds/linux.git
      </Link>
      ) and run{" "}
      <code className="text-foreground/80">git log --author="Urs Muff"</code>
      , or search the kernel mailing-list archive at{" "}
      <Link href="https://lore.kernel.org/" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
        lore.kernel.org
      </Link>
      . If you have specific commit hashes or patch URLs to anchor
      this page, refine through the Refine doorway below.
    </p>
  ),
};

export default content;
