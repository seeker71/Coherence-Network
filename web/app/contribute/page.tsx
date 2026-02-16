"use client";

import { useCallback, useMemo, useState } from "react";
import Link from "next/link";
import { getApiBase } from "@/lib/api";
import { useLiveRefresh } from "@/lib/live_refresh";

const API = getApiBase();

type Contributor = {
  id: string;
  name: string;
  type: string;
  email: string;
};

type IdeaQuestion = {
  question: string;
};

type Idea = {
  id: string;
  name: string;
  open_questions: IdeaQuestion[];
};

type SpecEntry = {
  spec_id: string;
  title: string;
};

type Vote = {
  voter_id: string;
  voter_type: "human" | "machine";
  decision: "yes" | "no";
  rationale?: string | null;
};

type ChangeRequest = {
  id: string;
  request_type: string;
  title: string;
  status: "open" | "approved" | "rejected" | "applied";
  proposer_id: string;
  approvals: number;
  rejections: number;
  payload: Record<string, unknown>;
  votes: Vote[];
  updated_at: string;
};

const REQUEST_TYPE_LABELS: Record<string, string> = {
  idea_create: "Idea Create",
  idea_update: "Idea Update",
  idea_add_question: "Idea Add Question",
  idea_answer_question: "Idea Answer Question",
  spec_create: "Spec Create",
  spec_update: "Spec Update",
};

export default function ContributePage() {
  const [contributors, setContributors] = useState<Contributor[]>([]);
  const [ideas, setIdeas] = useState<Idea[]>([]);
  const [specs, setSpecs] = useState<SpecEntry[]>([]);
  const [changeRequests, setChangeRequests] = useState<ChangeRequest[]>([]);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const [newContributorName, setNewContributorName] = useState("");
  const [newContributorEmail, setNewContributorEmail] = useState("");
  const [newContributorType, setNewContributorType] = useState<"HUMAN" | "SYSTEM">("HUMAN");

  const [proposerId, setProposerId] = useState("");
  const [reviewerId, setReviewerId] = useState("");
  const [reviewerType, setReviewerType] = useState<"human" | "machine">("human");
  const [voteNotes, setVoteNotes] = useState<Record<string, string>>({});

  const [ideaCreateId, setIdeaCreateId] = useState("");
  const [ideaCreateName, setIdeaCreateName] = useState("");
  const [ideaCreateDescription, setIdeaCreateDescription] = useState("");
  const [ideaCreatePotential, setIdeaCreatePotential] = useState("50");
  const [ideaCreateCost, setIdeaCreateCost] = useState("10");
  const [ideaCreateConfidence, setIdeaCreateConfidence] = useState("0.5");

  const [ideaUpdateId, setIdeaUpdateId] = useState("");
  const [ideaUpdateValue, setIdeaUpdateValue] = useState("");
  const [ideaUpdateCost, setIdeaUpdateCost] = useState("");
  const [ideaUpdateConfidence, setIdeaUpdateConfidence] = useState("");
  const [ideaUpdateStatus, setIdeaUpdateStatus] = useState("");

  const [questionIdeaId, setQuestionIdeaId] = useState("");
  const [questionText, setQuestionText] = useState("");
  const [questionValue, setQuestionValue] = useState("10");
  const [questionCost, setQuestionCost] = useState("2");

  const [answerIdeaId, setAnswerIdeaId] = useState("");
  const [answerQuestion, setAnswerQuestion] = useState("");
  const [answerText, setAnswerText] = useState("");
  const [answerDelta, setAnswerDelta] = useState("");

  const [specCreateId, setSpecCreateId] = useState("");
  const [specCreateTitle, setSpecCreateTitle] = useState("");
  const [specCreateSummary, setSpecCreateSummary] = useState("");
  const [specCreateIdeaId, setSpecCreateIdeaId] = useState("");

  const [specUpdateId, setSpecUpdateId] = useState("");
  const [specUpdateTitle, setSpecUpdateTitle] = useState("");
  const [specUpdateSummary, setSpecUpdateSummary] = useState("");

  const loadData = useCallback(async () => {
    setStatus((prev) => (prev === "ok" ? "ok" : "loading"));
    setError(null);
    try {
      const [contributorsRes, ideasRes, specsRes, crRes] = await Promise.all([
        fetch(`${API}/v1/contributors`, { cache: "no-store" }),
        fetch(`${API}/api/ideas`, { cache: "no-store" }),
        fetch(`${API}/api/spec-registry`, { cache: "no-store" }),
        fetch(`${API}/api/governance/change-requests`, { cache: "no-store" }),
      ]);
      if (!contributorsRes.ok || !ideasRes.ok || !specsRes.ok || !crRes.ok) {
        throw new Error(
          `HTTP ${contributorsRes.status}/${ideasRes.status}/${specsRes.status}/${crRes.status}`
        );
      }
      const [contributorsJson, ideasJson, specsJson, crJson] = await Promise.all([
        contributorsRes.json(),
        ideasRes.json(),
        specsRes.json(),
        crRes.json(),
      ]);
      const contributorRows = (Array.isArray(contributorsJson) ? contributorsJson : []) as Contributor[];
      const ideaRows = ((ideasJson?.ideas ?? []) as Idea[]).map((item) => ({
        id: item.id,
        name: item.name,
        open_questions: Array.isArray(item.open_questions) ? item.open_questions : [],
      }));
      const specRows = (Array.isArray(specsJson) ? specsJson : []) as SpecEntry[];
      const requestRows = (Array.isArray(crJson) ? crJson : []) as ChangeRequest[];

      setContributors(contributorRows);
      setIdeas(ideaRows);
      setSpecs(specRows);
      setChangeRequests(requestRows);
      if (!proposerId && contributorRows.length > 0) {
        setProposerId(contributorRows[0].id);
      }
      if (!reviewerId && contributorRows.length > 0) {
        setReviewerId(contributorRows[0].id);
      }
      if (!ideaUpdateId && ideaRows.length > 0) {
        setIdeaUpdateId(ideaRows[0].id);
      }
      if (!questionIdeaId && ideaRows.length > 0) {
        setQuestionIdeaId(ideaRows[0].id);
      }
      if (!answerIdeaId && ideaRows.length > 0) {
        setAnswerIdeaId(ideaRows[0].id);
      }
      if (!specUpdateId && specRows.length > 0) {
        setSpecUpdateId(specRows[0].spec_id);
      }
      setStatus("ok");
    } catch (e) {
      setStatus("error");
      setError(String(e));
    }
  }, [proposerId, reviewerId, ideaUpdateId, questionIdeaId, answerIdeaId, specUpdateId]);

  useLiveRefresh(loadData);

  const answerQuestions = useMemo(() => {
    const idea = ideas.find((row) => row.id === answerIdeaId);
    return idea?.open_questions ?? [];
  }, [ideas, answerIdeaId]);

  async function registerContributor() {
    if (!newContributorName.trim() || !newContributorEmail.trim()) return;
    setBusy("register");
    setError(null);
    try {
      const res = await fetch(`${API}/v1/contributors`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          type: newContributorType,
          name: newContributorName.trim(),
          email: newContributorEmail.trim(),
        }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(JSON.stringify(json));
      setNewContributorName("");
      setNewContributorEmail("");
      await loadData();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(null);
    }
  }

  async function createRequest(
    requestType:
      | "idea_create"
      | "idea_update"
      | "idea_add_question"
      | "idea_answer_question"
      | "spec_create"
      | "spec_update",
    title: string,
    payload: Record<string, unknown>
  ) {
    if (!proposerId) {
      setError("Select a proposer contributor first.");
      return;
    }
    setBusy(requestType);
    setError(null);
    try {
      const res = await fetch(`${API}/api/governance/change-requests`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          request_type: requestType,
          title,
          payload,
          proposer_id: proposerId,
          proposer_type: "human",
          auto_apply_on_approval: true,
        }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(JSON.stringify(json));
      await loadData();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(null);
    }
  }

  async function vote(changeRequestId: string, decision: "yes" | "no") {
    if (!reviewerId) {
      setError("Select a reviewer first.");
      return;
    }
    setBusy(`vote-${changeRequestId}-${decision}`);
    setError(null);
    try {
      const res = await fetch(`${API}/api/governance/change-requests/${encodeURIComponent(changeRequestId)}/votes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          voter_id: reviewerId,
          voter_type: reviewerType,
          decision,
          rationale: (voteNotes[changeRequestId] || "").trim() || undefined,
        }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(JSON.stringify(json));
      await loadData();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <main className="min-h-screen p-8 max-w-6xl mx-auto space-y-6">
      <div className="flex flex-wrap gap-3 text-sm">
        <Link href="/" className="text-muted-foreground hover:text-foreground">← Home</Link>
        <Link href="/contributors" className="text-muted-foreground hover:text-foreground">Contributors</Link>
        <Link href="/ideas" className="text-muted-foreground hover:text-foreground">Ideas</Link>
        <Link href="/specs" className="text-muted-foreground hover:text-foreground">Specs</Link>
        <Link href="/flow" className="text-muted-foreground hover:text-foreground">Flow</Link>
      </div>

      <h1 className="text-2xl font-bold">Contribution Console</h1>
      <p className="text-muted-foreground">
        Human flow: register as contributor, submit change requests (idea/spec/question), review with yes/no votes, and
        let approved requests auto-apply.
      </p>

      <section className="rounded border p-4 space-y-3">
        <h2 className="font-semibold">1) Register Contributor</h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-2 text-sm">
          <input
            className="rounded border px-3 py-2 bg-background"
            placeholder="Name"
            value={newContributorName}
            onChange={(e) => setNewContributorName(e.target.value)}
          />
          <input
            className="rounded border px-3 py-2 bg-background"
            placeholder="Email"
            value={newContributorEmail}
            onChange={(e) => setNewContributorEmail(e.target.value)}
          />
          <select
            className="rounded border px-3 py-2 bg-background"
            value={newContributorType}
            onChange={(e) => setNewContributorType(e.target.value as "HUMAN" | "SYSTEM")}
          >
            <option value="HUMAN">HUMAN</option>
            <option value="SYSTEM">SYSTEM</option>
          </select>
          <button
            type="button"
            className="rounded border px-3 py-2 hover:bg-accent"
            onClick={() => void registerContributor()}
            disabled={busy === "register"}
          >
            {busy === "register" ? "Registering…" : "Register"}
          </button>
        </div>
      </section>

      <section className="rounded border p-4 space-y-3">
        <h2 className="font-semibold">2) Select Proposer and Reviewer</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-sm">
          <select
            className="rounded border px-3 py-2 bg-background"
            value={proposerId}
            onChange={(e) => setProposerId(e.target.value)}
          >
            <option value="">Select proposer contributor</option>
            {contributors.map((item) => (
              <option key={item.id} value={item.id}>{item.name} ({item.id})</option>
            ))}
          </select>
          <select
            className="rounded border px-3 py-2 bg-background"
            value={reviewerId}
            onChange={(e) => setReviewerId(e.target.value)}
          >
            <option value="">Select reviewer contributor</option>
            {contributors.map((item) => (
              <option key={item.id} value={item.id}>{item.name} ({item.id})</option>
            ))}
          </select>
          <select
            className="rounded border px-3 py-2 bg-background"
            value={reviewerType}
            onChange={(e) => setReviewerType(e.target.value as "human" | "machine")}
          >
            <option value="human">human reviewer</option>
            <option value="machine">machine reviewer</option>
          </select>
        </div>
      </section>

      <section className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <article className="rounded border p-4 space-y-3">
          <h3 className="font-semibold">3a) Idea Create Request</h3>
          <div className="grid grid-cols-1 gap-2 text-sm">
            <input className="rounded border px-3 py-2 bg-background" placeholder="idea_id" value={ideaCreateId} onChange={(e) => setIdeaCreateId(e.target.value)} />
            <input className="rounded border px-3 py-2 bg-background" placeholder="name" value={ideaCreateName} onChange={(e) => setIdeaCreateName(e.target.value)} />
            <textarea className="rounded border px-3 py-2 bg-background" rows={3} placeholder="description" value={ideaCreateDescription} onChange={(e) => setIdeaCreateDescription(e.target.value)} />
            <div className="grid grid-cols-3 gap-2">
              <input className="rounded border px-3 py-2 bg-background" placeholder="potential_value" value={ideaCreatePotential} onChange={(e) => setIdeaCreatePotential(e.target.value)} />
              <input className="rounded border px-3 py-2 bg-background" placeholder="estimated_cost" value={ideaCreateCost} onChange={(e) => setIdeaCreateCost(e.target.value)} />
              <input className="rounded border px-3 py-2 bg-background" placeholder="confidence" value={ideaCreateConfidence} onChange={(e) => setIdeaCreateConfidence(e.target.value)} />
            </div>
            <button
              type="button"
              className="rounded border px-3 py-2 hover:bg-accent"
              disabled={busy === "idea_create"}
              onClick={() =>
                void createRequest("idea_create", `Create idea ${ideaCreateId}`, {
                  id: ideaCreateId.trim(),
                  name: ideaCreateName.trim(),
                  description: ideaCreateDescription.trim(),
                  potential_value: Number(ideaCreatePotential),
                  estimated_cost: Number(ideaCreateCost),
                  confidence: Number(ideaCreateConfidence),
                  interfaces: ["human:web", "machine:api"],
                })
              }
            >
              {busy === "idea_create" ? "Submitting…" : "Submit Idea Create Request"}
            </button>
          </div>
        </article>

        <article className="rounded border p-4 space-y-3">
          <h3 className="font-semibold">3b) Idea Update Request</h3>
          <div className="grid grid-cols-1 gap-2 text-sm">
            <select className="rounded border px-3 py-2 bg-background" value={ideaUpdateId} onChange={(e) => setIdeaUpdateId(e.target.value)}>
              <option value="">Select idea</option>
              {ideas.map((item) => (
                <option key={item.id} value={item.id}>{item.id}</option>
              ))}
            </select>
            <div className="grid grid-cols-2 gap-2">
              <input className="rounded border px-3 py-2 bg-background" placeholder="actual_value (optional)" value={ideaUpdateValue} onChange={(e) => setIdeaUpdateValue(e.target.value)} />
              <input className="rounded border px-3 py-2 bg-background" placeholder="actual_cost (optional)" value={ideaUpdateCost} onChange={(e) => setIdeaUpdateCost(e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <input className="rounded border px-3 py-2 bg-background" placeholder="confidence (optional)" value={ideaUpdateConfidence} onChange={(e) => setIdeaUpdateConfidence(e.target.value)} />
              <input className="rounded border px-3 py-2 bg-background" placeholder="manifestation_status (none|partial|validated)" value={ideaUpdateStatus} onChange={(e) => setIdeaUpdateStatus(e.target.value)} />
            </div>
            <button
              type="button"
              className="rounded border px-3 py-2 hover:bg-accent"
              disabled={busy === "idea_update"}
              onClick={() =>
                void createRequest("idea_update", `Update idea ${ideaUpdateId}`, {
                  idea_id: ideaUpdateId,
                  ...(ideaUpdateValue.trim() ? { actual_value: Number(ideaUpdateValue) } : {}),
                  ...(ideaUpdateCost.trim() ? { actual_cost: Number(ideaUpdateCost) } : {}),
                  ...(ideaUpdateConfidence.trim() ? { confidence: Number(ideaUpdateConfidence) } : {}),
                  ...(ideaUpdateStatus.trim() ? { manifestation_status: ideaUpdateStatus.trim() } : {}),
                })
              }
            >
              {busy === "idea_update" ? "Submitting…" : "Submit Idea Update Request"}
            </button>
          </div>
        </article>

        <article className="rounded border p-4 space-y-3">
          <h3 className="font-semibold">3c) Question Request (Add or Answer)</h3>
          <div className="grid grid-cols-1 gap-2 text-sm">
            <select className="rounded border px-3 py-2 bg-background" value={questionIdeaId} onChange={(e) => setQuestionIdeaId(e.target.value)}>
              <option value="">Select idea for new question</option>
              {ideas.map((item) => (
                <option key={item.id} value={item.id}>{item.id}</option>
              ))}
            </select>
            <input className="rounded border px-3 py-2 bg-background" placeholder="question text" value={questionText} onChange={(e) => setQuestionText(e.target.value)} />
            <div className="grid grid-cols-2 gap-2">
              <input className="rounded border px-3 py-2 bg-background" placeholder="value_to_whole" value={questionValue} onChange={(e) => setQuestionValue(e.target.value)} />
              <input className="rounded border px-3 py-2 bg-background" placeholder="estimated_cost" value={questionCost} onChange={(e) => setQuestionCost(e.target.value)} />
            </div>
            <button
              type="button"
              className="rounded border px-3 py-2 hover:bg-accent"
              disabled={busy === "idea_add_question"}
              onClick={() =>
                void createRequest("idea_add_question", `Add question to ${questionIdeaId}`, {
                  idea_id: questionIdeaId,
                  question: questionText.trim(),
                  value_to_whole: Number(questionValue),
                  estimated_cost: Number(questionCost),
                })
              }
            >
              {busy === "idea_add_question" ? "Submitting…" : "Submit Add-Question Request"}
            </button>
          </div>

          <div className="border-t pt-3 grid grid-cols-1 gap-2 text-sm">
            <select className="rounded border px-3 py-2 bg-background" value={answerIdeaId} onChange={(e) => setAnswerIdeaId(e.target.value)}>
              <option value="">Select idea for answer</option>
              {ideas.map((item) => (
                <option key={item.id} value={item.id}>{item.id}</option>
              ))}
            </select>
            <select className="rounded border px-3 py-2 bg-background" value={answerQuestion} onChange={(e) => setAnswerQuestion(e.target.value)}>
              <option value="">Select question</option>
              {answerQuestions.map((item) => (
                <option key={item.question} value={item.question}>{item.question}</option>
              ))}
            </select>
            <textarea className="rounded border px-3 py-2 bg-background" rows={3} placeholder="answer text" value={answerText} onChange={(e) => setAnswerText(e.target.value)} />
            <input className="rounded border px-3 py-2 bg-background" placeholder="measured_delta (optional)" value={answerDelta} onChange={(e) => setAnswerDelta(e.target.value)} />
            <button
              type="button"
              className="rounded border px-3 py-2 hover:bg-accent"
              disabled={busy === "idea_answer_question"}
              onClick={() =>
                void createRequest("idea_answer_question", `Answer question in ${answerIdeaId}`, {
                  idea_id: answerIdeaId,
                  question: answerQuestion,
                  answer: answerText.trim(),
                  ...(answerDelta.trim() ? { measured_delta: Number(answerDelta) } : {}),
                })
              }
            >
              {busy === "idea_answer_question" ? "Submitting…" : "Submit Answer Request"}
            </button>
          </div>
        </article>

        <article className="rounded border p-4 space-y-3">
          <h3 className="font-semibold">3d) Spec Create / Update Requests</h3>
          <div className="grid grid-cols-1 gap-2 text-sm">
            <input className="rounded border px-3 py-2 bg-background" placeholder="new spec_id" value={specCreateId} onChange={(e) => setSpecCreateId(e.target.value)} />
            <input className="rounded border px-3 py-2 bg-background" placeholder="new spec title" value={specCreateTitle} onChange={(e) => setSpecCreateTitle(e.target.value)} />
            <textarea className="rounded border px-3 py-2 bg-background" rows={3} placeholder="new spec summary" value={specCreateSummary} onChange={(e) => setSpecCreateSummary(e.target.value)} />
            <input className="rounded border px-3 py-2 bg-background" placeholder="related idea_id (optional)" value={specCreateIdeaId} onChange={(e) => setSpecCreateIdeaId(e.target.value)} />
            <button
              type="button"
              className="rounded border px-3 py-2 hover:bg-accent"
              disabled={busy === "spec_create"}
              onClick={() =>
                void createRequest("spec_create", `Create spec ${specCreateId}`, {
                  spec_id: specCreateId.trim(),
                  title: specCreateTitle.trim(),
                  summary: specCreateSummary.trim(),
                  idea_id: specCreateIdeaId.trim() || undefined,
                  created_by_contributor_id: proposerId,
                })
              }
            >
              {busy === "spec_create" ? "Submitting…" : "Submit Spec Create Request"}
            </button>
          </div>

          <div className="border-t pt-3 grid grid-cols-1 gap-2 text-sm">
            <select className="rounded border px-3 py-2 bg-background" value={specUpdateId} onChange={(e) => setSpecUpdateId(e.target.value)}>
              <option value="">Select spec</option>
              {specs.map((item) => (
                <option key={item.spec_id} value={item.spec_id}>{item.spec_id}</option>
              ))}
            </select>
            <input className="rounded border px-3 py-2 bg-background" placeholder="updated title (optional)" value={specUpdateTitle} onChange={(e) => setSpecUpdateTitle(e.target.value)} />
            <textarea className="rounded border px-3 py-2 bg-background" rows={3} placeholder="updated summary (optional)" value={specUpdateSummary} onChange={(e) => setSpecUpdateSummary(e.target.value)} />
            <button
              type="button"
              className="rounded border px-3 py-2 hover:bg-accent"
              disabled={busy === "spec_update"}
              onClick={() =>
                void createRequest("spec_update", `Update spec ${specUpdateId}`, {
                  spec_id: specUpdateId,
                  ...(specUpdateTitle.trim() ? { title: specUpdateTitle.trim() } : {}),
                  ...(specUpdateSummary.trim() ? { summary: specUpdateSummary.trim() } : {}),
                  updated_by_contributor_id: proposerId,
                })
              }
            >
              {busy === "spec_update" ? "Submitting…" : "Submit Spec Update Request"}
            </button>
          </div>
        </article>
      </section>

      <section className="rounded border p-4 space-y-3">
        <h2 className="font-semibold">4) Review Queue (Human or Machine Yes/No)</h2>
        <p className="text-sm text-muted-foreground">
          Default policy is one approval required. When contributor volume grows, increase `CHANGE_REQUEST_MIN_APPROVALS`.
        </p>
        <ul className="space-y-3 text-sm">
          {changeRequests.map((row) => (
            <li key={row.id} className="rounded border p-3 space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-medium">
                  {REQUEST_TYPE_LABELS[row.request_type] ?? row.request_type}: {row.title}
                </p>
                <p className="text-muted-foreground">
                  status <code>{row.status}</code> | approvals {row.approvals} | rejections {row.rejections}
                </p>
              </div>
              <p className="text-muted-foreground">
                proposer <code>{row.proposer_id}</code> | updated {row.updated_at}
              </p>
              <pre className="text-xs bg-muted p-2 rounded overflow-auto">{JSON.stringify(row.payload, null, 2)}</pre>
              <p className="text-xs text-muted-foreground">
                votes:{" "}
                {row.votes.length === 0
                  ? "none"
                  : row.votes.map((vote) => `${vote.voter_type}:${vote.voter_id}=${vote.decision}`).join(", ")}
              </p>
              <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_auto] gap-2">
                <input
                  className="rounded border px-3 py-2 bg-background"
                  placeholder="vote rationale (optional)"
                  value={voteNotes[row.id] || ""}
                  onChange={(e) => setVoteNotes((prev) => ({ ...prev, [row.id]: e.target.value }))}
                />
                <button
                  type="button"
                  className="rounded border px-3 py-2 hover:bg-accent"
                  disabled={busy === `vote-${row.id}-yes`}
                  onClick={() => void vote(row.id, "yes")}
                >
                  {busy === `vote-${row.id}-yes` ? "Saving…" : "Vote YES"}
                </button>
                <button
                  type="button"
                  className="rounded border px-3 py-2 hover:bg-accent"
                  disabled={busy === `vote-${row.id}-no`}
                  onClick={() => void vote(row.id, "no")}
                >
                  {busy === `vote-${row.id}-no` ? "Saving…" : "Vote NO"}
                </button>
              </div>
            </li>
          ))}
          {changeRequests.length === 0 && (
            <li className="text-muted-foreground">No change requests yet.</li>
          )}
        </ul>
      </section>

      <section className="rounded border p-4 space-y-2 text-sm">
        <h2 className="font-semibold">Machine API</h2>
        <p>Register contributor: <code>POST /v1/contributors</code></p>
        <p>Submit change request: <code>POST /api/governance/change-requests</code></p>
        <p>Vote yes/no: <code>POST /api/governance/change-requests/&lt;id&gt;/votes</code></p>
        <p>List specs: <code>GET /api/spec-registry</code> | list queue: <code>GET /api/governance/change-requests</code></p>
      </section>

      {status === "loading" && <p className="text-muted-foreground">Loading…</p>}
      {status === "error" && <p className="text-destructive">Error: {error}</p>}
      {error && status !== "error" && <p className="text-destructive">Error: {error}</p>}
    </main>
  );
}
