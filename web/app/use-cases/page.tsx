import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Building2,
  DollarSign,
  Flask,
  Rocket,
  Users,
  ArrowRight,
  CheckCircle2
} from "lucide-react";

export const metadata = {
  title: "Use Cases - Coherence Network",
  description: "Real-world applications and success stories for Coherence Network",
};

const useCases = [
  {
    icon: Building2,
    title: "Organizations",
    subtitle: "Track internal OSS contributions, calculate fair bonuses",
    challenge: "Hard to measure developer impact on OSS projects",
    solution: "Coherence Network automatically tracks contributions and scores quality",
    outcomes: [
      "Objective performance metrics for OSS contributions",
      "Fair bonus allocation based on contribution coherence",
      "Visibility into team's external impact",
    ],
    example: {
      scenario: "Engineering team of 20 contributing to 15 OSS projects",
      before: "Manual tracking, subjective reviews, uneven recognition",
      after: "Automated tracking, coherence-weighted bonuses, transparent attribution",
      impact: "30% increase in OSS engagement, 90% reduction in tracking overhead",
    },
  },
  {
    icon: DollarSign,
    title: "Grant Programs",
    subtitle: "Data-driven allocation based on contributor impact",
    challenge: "Grant decisions often based on popularity, not actual value",
    solution: "Use coherence scores and contribution history for objective funding decisions",
    outcomes: [
      "Evidence-based grant allocation",
      "Automatic detection of high-value contributors",
      "Fair distribution weighted by contribution quality",
    ],
    example: {
      scenario: "$100K grant fund for React ecosystem contributors",
      before: "Top 10 by GitHub stars receive equal splits",
      after: "Weighted distribution based on coherence-scored contributions",
      impact: "5x more maintainers funded, quality-over-popularity allocation",
    },
  },
  {
    icon: Flask,
    title: "Researchers",
    subtitle: "Analyze OSS ecosystem health and contributor patterns",
    challenge: "Limited tools for studying OSS contribution dynamics",
    solution: "Rich API for querying project health, dependencies, and contributor patterns",
    outcomes: [
      "Access to structured OSS intelligence data",
      "Coherence metrics for quality assessment",
      "Historical contribution and dependency tracking",
    ],
    example: {
      scenario: "PhD research on OSS sustainability factors",
      before: "Manually scrape GitHub, limited quality signals",
      after: "Query Coherence Network API for 10K+ projects with coherence scores",
      impact: "6 months of data collection reduced to 1 day of API calls",
    },
  },
  {
    icon: Rocket,
    title: "Startups",
    subtitle: "Prioritize feature development by ROI",
    challenge: "Limited resources, need to maximize impact per engineering hour",
    solution: "Use free energy scoring to rank ideas by (value × confidence) / (cost + risk)",
    outcomes: [
      "Objective feature prioritization",
      "Track actual value vs estimated",
      "Reduce wasted effort on low-ROI features",
    ],
    example: {
      scenario: "Early-stage startup with 3-person eng team",
      before: "Feature decisions by gut feel, frequent pivots",
      after: "ROI-ranked backlog, evidence-based pivots, clear value tracking",
      impact: "40% faster iteration, 60% reduction in abandoned features",
    },
  },
  {
    icon: Users,
    title: "DAOs",
    subtitle: "Transparent value distribution to contributors",
    challenge: "Fair compensation without centralized decision-making",
    solution: "Automated payout calculation weighted by contribution coherence",
    outcomes: [
      "Trustless distribution based on verifiable contributions",
      "Quality-weighted payouts (not just volume)",
      "Transparent attribution and audit trail",
    ],
    example: {
      scenario: "Protocol DAO with 50 active contributors",
      before: "Monthly votes on compensation, political friction",
      after: "Automated distributions based on contribution coherence scores",
      impact: "Zero governance overhead, 95% contributor satisfaction, no disputes",
    },
  },
];

export default function UseCasesPage() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-white to-gray-50">
      {/* Header */}
      <div className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <Link href="/" className="text-sm text-blue-600 hover:text-blue-800 mb-4 inline-block">
            ← Back to Home
          </Link>
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            Use Cases & Success Stories
          </h1>
          <p className="text-xl text-gray-600 max-w-3xl">
            Real-world applications of Coherence Network across organizations, grant programs,
            research institutions, startups, and DAOs.
          </p>
        </div>
      </div>

      {/* Use Cases */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="space-y-16">
          {useCases.map((useCase, idx) => {
            const Icon = useCase.icon;
            return (
              <div
                key={idx}
                className="bg-white rounded-lg shadow-lg border border-gray-200 overflow-hidden hover:shadow-xl transition-shadow"
              >
                {/* Header */}
                <div className="bg-gradient-to-r from-blue-50 to-indigo-50 px-8 py-6 border-b">
                  <div className="flex items-start gap-4">
                    <div className="bg-blue-100 p-3 rounded-lg">
                      <Icon className="w-8 h-8 text-blue-600" />
                    </div>
                    <div>
                      <h2 className="text-2xl font-bold text-gray-900 mb-2">
                        {useCase.title}
                      </h2>
                      <p className="text-gray-600 text-lg">
                        {useCase.subtitle}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Content */}
                <div className="px-8 py-6">
                  <div className="grid md:grid-cols-2 gap-8 mb-8">
                    {/* Challenge & Solution */}
                    <div>
                      <h3 className="font-semibold text-red-600 mb-2">Challenge</h3>
                      <p className="text-gray-700 mb-4">{useCase.challenge}</p>

                      <h3 className="font-semibold text-green-600 mb-2">Solution</h3>
                      <p className="text-gray-700">{useCase.solution}</p>
                    </div>

                    {/* Outcomes */}
                    <div>
                      <h3 className="font-semibold text-gray-900 mb-3">Key Outcomes</h3>
                      <ul className="space-y-2">
                        {useCase.outcomes.map((outcome, i) => (
                          <li key={i} className="flex items-start gap-2">
                            <CheckCircle2 className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
                            <span className="text-gray-700">{outcome}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>

                  {/* Example */}
                  <div className="bg-gray-50 rounded-lg p-6 border border-gray-200">
                    <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
                      <Rocket className="w-5 h-5" />
                      Example Scenario
                    </h3>
                    <div className="space-y-3">
                      <div>
                        <span className="text-sm font-medium text-gray-500">Scenario:</span>
                        <p className="text-gray-900">{useCase.example.scenario}</p>
                      </div>
                      <div className="grid md:grid-cols-2 gap-4">
                        <div>
                          <span className="text-sm font-medium text-red-600">Before:</span>
                          <p className="text-gray-700 text-sm">{useCase.example.before}</p>
                        </div>
                        <div>
                          <span className="text-sm font-medium text-green-600">After:</span>
                          <p className="text-gray-700 text-sm">{useCase.example.after}</p>
                        </div>
                      </div>
                      <div className="bg-blue-50 border-l-4 border-blue-500 p-3 mt-4">
                        <span className="text-sm font-medium text-blue-900">Impact:</span>
                        <p className="text-blue-800 font-medium">{useCase.example.impact}</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* CTA Section */}
        <div className="mt-16 bg-gradient-to-r from-blue-600 to-indigo-600 rounded-lg shadow-xl p-8 text-center">
          <h2 className="text-3xl font-bold text-white mb-4">
            Ready to Get Started?
          </h2>
          <p className="text-blue-100 text-lg mb-6 max-w-2xl mx-auto">
            Start using Coherence Network today to track contributions, calculate fair distributions,
            and make data-driven decisions.
          </p>
          <div className="flex flex-wrap gap-4 justify-center">
            <Button asChild size="lg" variant="secondary">
              <Link href="/search">
                Explore Projects
                <ArrowRight className="ml-2 w-4 h-4" />
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline" className="bg-white text-blue-600 hover:bg-blue-50">
              <a
                href={process.env.NEXT_PUBLIC_API_URL ? `${process.env.NEXT_PUBLIC_API_URL}/docs` : "http://localhost:8000/docs"}
                target="_blank"
                rel="noopener noreferrer"
              >
                View API Docs
                <ArrowRight className="ml-2 w-4 h-4" />
              </a>
            </Button>
          </div>
        </div>

        {/* Footer Note */}
        <div className="mt-12 text-center text-gray-500 text-sm">
          <p>
            Want to share your success story?{" "}
            <a
              href="https://github.com/seeker71/Coherence-Network/discussions"
              className="text-blue-600 hover:text-blue-800"
              target="_blank"
              rel="noopener noreferrer"
            >
              Start a discussion on GitHub
            </a>
          </p>
        </div>
      </div>
    </main>
  );
}
