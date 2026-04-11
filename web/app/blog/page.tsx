import type { Metadata } from "next";
import { loadPublicWebConfig } from "@/lib/app-config";

const _WEB_UI = loadPublicWebConfig().webUiBaseUrl;

export const metadata: Metadata = {
  title: "Blog | Coherence Network",
  description: "Learnings from running 842 tasks across 6 AI providers with data-driven selection.",
  openGraph: {
    title: "We ran 842 tasks across 6 AI providers. Here's what the data says.",
    description: "Claude, Codex, Gemini, Cursor, Ollama — benchmarked head-to-head with Thompson Sampling. Real data, real tasks, no synthetic benchmarks.",
    url: `${_WEB_UI}/blog`,
  },
};

export default function BlogPage() {
  return (
    <main id="main-content" className="mx-auto max-w-2xl px-4 sm:px-6 py-12 space-y-10">
      <article className="prose prose-stone dark:prose-invert prose-headings:tracking-tight prose-a:text-amber-600 dark:prose-a:text-amber-400 max-w-none">
        <h1 className="text-3xl font-bold tracking-tight">
          We ran 842 tasks across 6 AI providers. Here&apos;s what the data says.
        </h1>
        <p className="text-muted-foreground text-lg leading-relaxed">
          March 2026 — No synthetic benchmarks. Real spec writing, real implementations,
          real code reviews. Thompson Sampling picked the provider. The data picked the winner.
        </p>

        <hr className="border-border/30 my-8" />

        <h2>The setup</h2>
        <p>
          We needed to run hundreds of tasks through an automated pipeline: write specs,
          implement features, write tests, review code. Instead of picking one AI provider,
          we asked: what if the system learned which provider works best for each task type?
        </p>
        <p>
          Six providers, all running on the same machine, same codebase, same task descriptions.
          Thompson Sampling — a classic multi-armed bandit algorithm — selected which provider
          got each task based on historical success rates, with a recency bias so the system
          reacts quickly to changes.
        </p>

        <h2>The providers</h2>
        <div className="not-prose my-6">
          <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/30 text-left">
                  <th className="p-3 font-medium">Provider</th>
                  <th className="p-3 font-medium text-right">Success</th>
                  <th className="p-3 font-medium text-right">Runs</th>
                  <th className="p-3 font-medium text-right">Avg Speed</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/20">
                <tr><td className="p-3">Claude Code</td><td className="p-3 text-right text-emerald-500">96%</td><td className="p-3 text-right">108</td><td className="p-3 text-right">121s</td></tr>
                <tr><td className="p-3">Cursor Agent</td><td className="p-3 text-right text-emerald-500">96%</td><td className="p-3 text-right">94</td><td className="p-3 text-right">125s</td></tr>
                <tr><td className="p-3">OpenAI Codex</td><td className="p-3 text-right text-emerald-500">91%</td><td className="p-3 text-right">169</td><td className="p-3 text-right">38s</td></tr>
                <tr><td className="p-3">Gemini CLI</td><td className="p-3 text-right text-amber-500">83%</td><td className="p-3 text-right">35</td><td className="p-3 text-right">214s</td></tr>
                <tr><td className="p-3">Ollama Local</td><td className="p-3 text-right text-emerald-500">100%</td><td className="p-3 text-right">18</td><td className="p-3 text-right">294s</td></tr>
                <tr><td className="p-3">Ollama Cloud</td><td className="p-3 text-right text-emerald-500">100%</td><td className="p-3 text-right">15</td><td className="p-3 text-right">8s</td></tr>
              </tbody>
            </table>
          </div>
        </div>

        <h2>What surprised us</h2>

        <h3>Codex is the speed champion</h3>
        <p>
          At 38 seconds average with 91% success, Codex handled the most volume. It got 169 runs
          because Thompson Sampling kept selecting it — fast + reliable = high selection probability.
          Its failures were mostly CLI argument issues that we fixed and never recurred.
        </p>

        <h3>Ollama Cloud was the sleeper</h3>
        <p>
          8 seconds average. 100% success. GLM-5 via Ollama Cloud was the fastest provider by far.
          It got fewer runs (15) because it started with no data and Thompson Sampling needed time to
          discover its quality. But once it had 5+ samples, its selection probability climbed rapidly.
        </p>

        <h3>Gemini needed a one-character fix</h3>
        <p>
          Gemini had 0% success for its first 6 runs. All timeouts. No output captured. We were
          about to write it off. Then we discovered the root cause: the {`-y`} flag (auto-approve
          tool use) was missing. Without it, Gemini would try to use tools, wait for interactive
          approval that never came, and hang until timeout. One flag. 0% to 83%.
        </p>

        <h3>False positives are worse than failures</h3>
        <p>
          Ollama and OpenRouter reported &quot;success&quot; on implementation tasks — but they have no tools.
          They generated confident text describing the files they &quot;created&quot; without actually creating
          anything. We added git-diff validation: after every impl/spec/test task, the runner checks
          if files actually changed. Text-only providers are now restricted to review tasks where
          text output IS the deliverable.
        </p>

        <h3>Timeouts should be data-driven</h3>
        <p>
          We started with a flat 300-second timeout for everything. But Codex finishes specs in 20
          seconds while Claude needs 180 seconds for complex implementations. Now each provider gets
          a timeout of 2.5x its p90 duration, per task type. A Codex spec gets 50 seconds. A Claude
          impl gets 450 seconds. Tight enough to catch real hangs, loose enough to not kill slow-but-working tasks.
        </p>

        <h2>How Thompson Sampling works here</h2>
        <p>
          Each provider is a &quot;slot&quot; in a multi-armed bandit. For every task, the system draws a random
          sample from each provider&apos;s Beta distribution (shaped by its success/failure history) and picks
          the highest draw. This naturally balances exploration (trying under-sampled providers) with
          exploitation (favoring proven winners).
        </p>
        <p>
          We added recency weighting: the last 5 runs count for 60% of the signal, all-time history
          for 40%. This means if a provider degrades (rate limit hit, API change, model update), the
          system reacts within a few runs instead of being anchored by old data.
        </p>

        <h2>The infrastructure</h2>
        <p>
          Everything runs through a single abstraction called SlotSelector. It works for provider
          selection, prompt variant testing, model selection within a provider — any decision point
          where you want data to pick the winner instead of a human.
        </p>
        <p>
          Measurements are stored locally per node and pushed to a federation hub. Multiple machines
          can run tasks independently, and the hub aggregates their data. A Mac running 6 providers
          and a VPS running 2 providers both contribute to the same picture.
        </p>

        <h2>Try it yourself</h2>
        <p>
          The entire system is open source. Clone the repo, run the local runner, and your machine
          joins the network. Thompson Sampling starts learning from your providers immediately.
        </p>
        <div className="not-prose my-6 rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3">
          <pre className="text-sm overflow-x-auto"><code>{`git clone https://github.com/seeker71/Coherence-Network.git
cd Coherence-Network/api
pip install -e .
python scripts/local_runner.py --timeout 300`}</code></pre>
          <p className="text-sm text-muted-foreground">
            Auto-detects your providers. No config needed.
          </p>
        </div>

        <p>
          Or install the skill in any agent that supports the AgentSkills standard:
        </p>
        <div className="not-prose my-6 rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6">
          <pre className="text-sm"><code>clawhub install coherence-network</code></pre>
        </div>

        <p>
          The data is at{" "}
          <a href={`${_WEB_UI}/automation`} className="text-amber-600 dark:text-amber-400 hover:underline">
            coherencycoin.com/automation
          </a>
          . The ideas are at{" "}
          <a href={`${_WEB_UI}/ideas`} className="text-amber-600 dark:text-amber-400 hover:underline">
            coherencycoin.com/ideas
          </a>
          . The code is at{" "}
          <a href="https://github.com/seeker71/Coherence-Network" className="text-amber-600 dark:text-amber-400 hover:underline">
            github.com/seeker71/Coherence-Network
          </a>
          .
        </p>
      </article>

      <section className="border-t border-border/20 pt-8 text-center space-y-3">
        <p className="text-sm text-muted-foreground uppercase tracking-wider">Where to go next</p>
        <div className="flex justify-center gap-6 text-sm">
          <a href="/ideas" className="text-amber-600 dark:text-amber-400 hover:underline">Explore ideas</a>
          <a href="/resonance" className="text-amber-600 dark:text-amber-400 hover:underline">Resonance feed</a>
          <a href="/invest" className="text-amber-600 dark:text-amber-400 hover:underline">Invest</a>
        </div>
      </section>
    </main>
  );
}
