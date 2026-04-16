"use client";

import { useCallback, useMemo, useState } from "react";
import Link from "next/link";
import { getApiBase } from "@/lib/api";
import { useLiveRefresh } from "@/lib/live_refresh";
import { useT } from "@/components/MessagesProvider";
import type { IdeaQuestion } from "@/lib/types";

const API = getApiBase();

type Contributor = {
  id: string;
  name: string;
  type: string;
  email: string;
};

type Idea = {
  id: string;
  name: string;
  open_questions: IdeaQuestion[];
};

type SpecEntry = {
  spec_id: string;
  title: string;
  potential_value?: number;
  estimated_cost?: number;
  actual_value?: number;
  actual_cost?: number;
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
  const t = useT();
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
  const [specCreatePotentialValue, setSpecCreatePotentialValue] = useState("0");
  const [specCreateEstimatedCost, setSpecCreateEstimatedCost] = useState("0");
  const [specCreateActualValue, setSpecCreateActualValue] = useState("0");
  const [specCreateActualCost, setSpecCreateActualCost] = useState("0");

  const [specUpdateId, setSpecUpdateId] = useState("");
  const [specUpdateTitle, setSpecUpdateTitle] = useState("");
  const [specUpdateSummary, setSpecUpdateSummary] = useState("");
  const [specUpdatePotentialValue, setSpecUpdatePotentialValue] = useState("");
  const [specUpdateEstimatedCost, setSpecUpdateEstimatedCost] = useState("");
  const [specUpdateActualValue, setSpecUpdateActualValue] = useState("");
  const [specUpdateActualCost, setSpecUpdateActualCost] = useState("");

  const loadData = useCallback(async () => {
    setStatus((prev) => (prev === "ok" ? "ok" : "loading"));
    setError(null);
    try {
      const [contributorsRes, ideasRes, specsRes, crRes] = await Promise.all([
        fetch(`${API}/api/contributors`, { cache: "no-store" }),
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
      const contributorRows = (contributorsJson?.items ?? (Array.isArray(contributorsJson) ? contributorsJson : [])) as Contributor[];
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
      const res = await fetch(`${API}/api/contributors`, {
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
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8 max-w-6xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight mb-2">{t("contribute.title")}</h1>
        <p className="text-muted-foreground max-w-2xl leading-relaxed">
          {t("contribute.introLede")}
        </p>
      </div>

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-3">
        <h2 className="text-xl font-semibold">{t("contribute.registerHeading")}</h2>
        <p className="text-sm text-muted-foreground">{t("contribute.registerBody")}</p>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-2 text-sm">
          <div className="space-y-1">
            <label htmlFor="contributor-name" className="text-xs text-muted-foreground">Name</label>
            <input
              id="contributor-name"
              className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2"
              placeholder={t("contribute.namePlaceholder")}
              value={newContributorName}
              onChange={(e) => setNewContributorName(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <label htmlFor="contributor-email" className="text-xs text-muted-foreground">{t("contribute.emailPlaceholder")}</label>
            <input
              id="contributor-email"
              className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2"
              placeholder={t("contribute.emailPlaceholder")}
              value={newContributorEmail}
              onChange={(e) => setNewContributorEmail(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <label htmlFor="contributor-type" className="text-xs text-muted-foreground">Type</label>
            <select
              id="contributor-type"
              className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2"
              value={newContributorType}
              onChange={(e) => setNewContributorType(e.target.value as "HUMAN" | "SYSTEM")}
            >
              <option value="HUMAN">HUMAN</option>
              <option value="SYSTEM">SYSTEM</option>
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground invisible">{t("contribute.action")}</label>
            <button
              type="button"
              className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2 hover:bg-accent"
              onClick={() => {
                if (!newContributorName.trim() || !newContributorEmail.trim()) return;
                void registerContributor();
              }}
              disabled={busy === "register" || !newContributorName.trim() || !newContributorEmail.trim()}
            >
              {busy === "register" ? t("contribute.registering") : t("contribute.register")}
            </button>
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3">
        <h2 className="text-xl font-semibold">{t("contribute.selectPair")}</h2>
        <p className="text-sm text-muted-foreground">{t("contribute.selectPairBody")}</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-sm">
          <select
            className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2"
            value={proposerId}
            onChange={(e) => setProposerId(e.target.value)}
          >
            <option value="">{t("contribute.selectProposer")}</option>
            {contributors.map((item) => (
              <option key={item.id} value={item.id}>{item.name} ({item.id})</option>
            ))}
          </select>
          <select
            className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2"
            value={reviewerId}
            onChange={(e) => setReviewerId(e.target.value)}
          >
            <option value="">{t("contribute.selectReviewer")}</option>
            {contributors.map((item) => (
              <option key={item.id} value={item.id}>{item.name} ({item.id})</option>
            ))}
          </select>
          <select
            className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2"
            value={reviewerType}
            onChange={(e) => setReviewerType(e.target.value as "human" | "machine")}
          >
            <option value="human">human reviewer</option>
            <option value="machine">machine reviewer</option>
          </select>
        </div>
      </section>

      <section className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <article className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3">
          <h3 className="text-xl font-semibold">{t("contribute.createIdea")}</h3>
          <p className="text-sm text-muted-foreground">{t("contribute.createIdeaBody")}</p>
          <div className="grid grid-cols-1 gap-2 text-sm">
            <div className="space-y-1">
              <label htmlFor="idea-create-id" className="text-xs text-muted-foreground">{t("contribute.ideaIdLabel")}</label>
              <input id="idea-create-id" className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2" placeholder="idea_id" value={ideaCreateId} onChange={(e) => setIdeaCreateId(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label htmlFor="idea-create-name" className="text-xs text-muted-foreground">Name</label>
              <input id="idea-create-name" className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2" placeholder="name" value={ideaCreateName} onChange={(e) => setIdeaCreateName(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label htmlFor="idea-create-desc" className="text-xs text-muted-foreground">{t("contribute.descriptionLabel")}</label>
              <textarea id="idea-create-desc" className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2" rows={3} placeholder="description" value={ideaCreateDescription} onChange={(e) => setIdeaCreateDescription(e.target.value)} />
            </div>
            <div className="grid grid-cols-3 gap-2">
              <div className="space-y-1">
                <label htmlFor="idea-create-potential" className="text-xs text-muted-foreground">{t("contribute.potentialValue")}</label>
                <input id="idea-create-potential" className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2" placeholder="potential_value" value={ideaCreatePotential} onChange={(e) => setIdeaCreatePotential(e.target.value)} />
              </div>
              <div className="space-y-1">
                <label htmlFor="idea-create-cost" className="text-xs text-muted-foreground">{t("contribute.estimatedCost")}</label>
                <input id="idea-create-cost" className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2" placeholder="estimated_cost" value={ideaCreateCost} onChange={(e) => setIdeaCreateCost(e.target.value)} />
              </div>
              <div className="space-y-1">
                <label htmlFor="idea-create-confidence" className="text-xs text-muted-foreground">{t("contribute.confidence")}</label>
                <input id="idea-create-confidence" className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2" placeholder="confidence" value={ideaCreateConfidence} onChange={(e) => setIdeaCreateConfidence(e.target.value)} />
              </div>
            </div>
            <button
              type="button"
              className="rounded-xl border border-border/40 bg-card/60 px-3 py-2 hover:bg-accent"
              disabled={busy === "idea_create" || !ideaCreateName.trim() || !ideaCreateDescription.trim()}
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
              {busy === "idea_create" ? t("contribute.submitting") : t("contribute.submitIdeaCreate")}
            </button>
          </div>
        </article>

        <article className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3">
          <h3 className="text-xl font-semibold">{t("contribute.updateIdea")}</h3>
          <p className="text-sm text-muted-foreground">{t("contribute.updateIdeaBody")}</p>
          <div className="grid grid-cols-1 gap-2 text-sm">
            <select className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2" value={ideaUpdateId} onChange={(e) => setIdeaUpdateId(e.target.value)}>
              <option value="">{t("contribute.selectIdea")}</option>
              {ideas.map((item) => (
                <option key={item.id} value={item.id}>{item.id}</option>
              ))}
            </select>
            <div className="grid grid-cols-2 gap-2">
              <input className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2" placeholder="actual_value (optional)" value={ideaUpdateValue} onChange={(e) => setIdeaUpdateValue(e.target.value)} />
              <input className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2" placeholder="actual_cost (optional)" value={ideaUpdateCost} onChange={(e) => setIdeaUpdateCost(e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <input className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2" placeholder="confidence (optional)" value={ideaUpdateConfidence} onChange={(e) => setIdeaUpdateConfidence(e.target.value)} />
              <input className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2" placeholder="manifestation_status (none|partial|validated)" value={ideaUpdateStatus} onChange={(e) => setIdeaUpdateStatus(e.target.value)} />
            </div>
            <button
              type="button"
              className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2 hover:bg-accent transition-colors"
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
              {busy === "idea_update" ? t("contribute.submitting") : t("contribute.submitIdeaUpdate")}
            </button>
          </div>
        </article>

        <article className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3">
          <h3 className="text-xl font-semibold">{t("contribute.questions")}</h3>
          <p className="text-sm text-muted-foreground">{t("contribute.questionsBody")}</p>
          <div className="grid grid-cols-1 gap-2 text-sm">
            <select className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2" value={questionIdeaId} onChange={(e) => setQuestionIdeaId(e.target.value)}>
              <option value="">{t("contribute.selectIdeaQuestion")}</option>
              {ideas.map((item) => (
                <option key={item.id} value={item.id}>{item.id}</option>
              ))}
            </select>
            <input className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2" placeholder="question text" value={questionText} onChange={(e) => setQuestionText(e.target.value)} />
            <div className="grid grid-cols-2 gap-2">
              <input className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2" placeholder="value_to_whole" value={questionValue} onChange={(e) => setQuestionValue(e.target.value)} />
              <input className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2" placeholder="estimated_cost" value={questionCost} onChange={(e) => setQuestionCost(e.target.value)} />
            </div>
            <button
              type="button"
              className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2 hover:bg-accent transition-colors"
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
              {busy === "idea_add_question" ? t("contribute.submitting") : t("contribute.submitAddQuestion")}
            </button>
          </div>

          <div className="border-t pt-3 grid grid-cols-1 gap-2 text-sm">
            <select className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2" value={answerIdeaId} onChange={(e) => setAnswerIdeaId(e.target.value)}>
              <option value="">{t("contribute.selectIdeaAnswer")}</option>
              {ideas.map((item) => (
                <option key={item.id} value={item.id}>{item.id}</option>
              ))}
            </select>
            <select className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2" value={answerQuestion} onChange={(e) => setAnswerQuestion(e.target.value)}>
              <option value="">{t("contribute.selectQuestion")}</option>
              {answerQuestions.map((item) => (
                <option key={item.question} value={item.question}>{item.question}</option>
              ))}
            </select>
            <textarea className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2" rows={3} placeholder="answer text" value={answerText} onChange={(e) => setAnswerText(e.target.value)} />
            <input className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2" placeholder="measured_delta (optional)" value={answerDelta} onChange={(e) => setAnswerDelta(e.target.value)} />
            <button
              type="button"
              className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2 hover:bg-accent transition-colors"
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
              {busy === "idea_answer_question" ? t("contribute.submitting") : t("contribute.submitAnswer")}
            </button>
          </div>
        </article>

        <article className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3">
          <h3 className="text-xl font-semibold">{t("contribute.specs")}</h3>
          <p className="text-sm text-muted-foreground">{t("contribute.specsBody")}</p>
          <div className="grid grid-cols-1 gap-2 text-sm">
            <input className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2" placeholder="new spec_id" value={specCreateId} onChange={(e) => setSpecCreateId(e.target.value)} />
            <input className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2" placeholder="new spec title" value={specCreateTitle} onChange={(e) => setSpecCreateTitle(e.target.value)} />
            <textarea className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2" rows={3} placeholder="new spec summary" value={specCreateSummary} onChange={(e) => setSpecCreateSummary(e.target.value)} />
            <input className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2" placeholder="related idea_id (optional)" value={specCreateIdeaId} onChange={(e) => setSpecCreateIdeaId(e.target.value)} />
            <input
              className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2"
              placeholder="potential_value (default 0)"
              value={specCreatePotentialValue}
              onChange={(e) => setSpecCreatePotentialValue(e.target.value)}
            />
            <input
              className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2"
              placeholder="estimated_cost (default 0)"
              value={specCreateEstimatedCost}
              onChange={(e) => setSpecCreateEstimatedCost(e.target.value)}
            />
            <input
              className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2"
              placeholder="actual_value (default 0)"
              value={specCreateActualValue}
              onChange={(e) => setSpecCreateActualValue(e.target.value)}
            />
            <input
              className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2"
              placeholder="actual_cost (default 0)"
              value={specCreateActualCost}
              onChange={(e) => setSpecCreateActualCost(e.target.value)}
            />
            <button
              type="button"
              className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2 hover:bg-accent transition-colors"
              disabled={busy === "spec_create"}
              onClick={() =>
                void createRequest("spec_create", `Create spec ${specCreateId}`, {
                  spec_id: specCreateId.trim(),
                  title: specCreateTitle.trim(),
                  summary: specCreateSummary.trim(),
                  idea_id: specCreateIdeaId.trim() || undefined,
                  potential_value: Number(specCreatePotentialValue || "0"),
                  estimated_cost: Number(specCreateEstimatedCost || "0"),
                  actual_value: Number(specCreateActualValue || "0"),
                  actual_cost: Number(specCreateActualCost || "0"),
                  created_by_contributor_id: proposerId,
                })
              }
            >
              {busy === "spec_create" ? t("contribute.submitting") : t("contribute.submitSpecCreate")}
            </button>
          </div>

          <div className="border-t pt-3 grid grid-cols-1 gap-2 text-sm">
            <select className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2" value={specUpdateId} onChange={(e) => setSpecUpdateId(e.target.value)}>
              <option value="">{t("contribute.selectSpec")}</option>
              {specs.map((item) => (
                <option key={item.spec_id} value={item.spec_id}>{item.spec_id}</option>
              ))}
            </select>
            <input className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2" placeholder="updated title (optional)" value={specUpdateTitle} onChange={(e) => setSpecUpdateTitle(e.target.value)} />
            <textarea className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2" rows={3} placeholder="updated summary (optional)" value={specUpdateSummary} onChange={(e) => setSpecUpdateSummary(e.target.value)} />
            <input
              className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2"
              placeholder="potential_value (optional)"
              value={specUpdatePotentialValue}
              onChange={(e) => setSpecUpdatePotentialValue(e.target.value)}
            />
            <input
              className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2"
              placeholder="estimated_cost (optional)"
              value={specUpdateEstimatedCost}
              onChange={(e) => setSpecUpdateEstimatedCost(e.target.value)}
            />
            <input
              className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2"
              placeholder="actual_value (optional)"
              value={specUpdateActualValue}
              onChange={(e) => setSpecUpdateActualValue(e.target.value)}
            />
            <input
              className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2"
              placeholder="actual_cost (optional)"
              value={specUpdateActualCost}
              onChange={(e) => setSpecUpdateActualCost(e.target.value)}
            />
            <button
              type="button"
              className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2 hover:bg-accent transition-colors"
              disabled={busy === "spec_update"}
              onClick={() =>
                void createRequest("spec_update", `Update spec ${specUpdateId}`, {
                  spec_id: specUpdateId,
                  ...(specUpdateTitle.trim() ? { title: specUpdateTitle.trim() } : {}),
                  ...(specUpdateSummary.trim() ? { summary: specUpdateSummary.trim() } : {}),
                  ...(specUpdatePotentialValue.trim() ? { potential_value: Number(specUpdatePotentialValue) } : {}),
                  ...(specUpdateEstimatedCost.trim() ? { estimated_cost: Number(specUpdateEstimatedCost) } : {}),
                  ...(specUpdateActualValue.trim() ? { actual_value: Number(specUpdateActualValue) } : {}),
                  ...(specUpdateActualCost.trim() ? { actual_cost: Number(specUpdateActualCost) } : {}),
                  updated_by_contributor_id: proposerId,
                })
              }
            >
              {busy === "spec_update" ? t("contribute.submitting") : t("contribute.submitSpecUpdate")}
            </button>
          </div>
        </article>
      </section>

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3">
        <h2 className="text-xl font-semibold">{t("contribute.reviewQueue")}</h2>
        <p className="text-sm text-muted-foreground">
          {t("contribute.approvalPolicy")}
        </p>
        <ul className="space-y-3 text-sm">
          {changeRequests.map((row) => (
            <li key={row.id} className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-2">
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
                  className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2"
                  placeholder="vote rationale (optional)"
                  value={voteNotes[row.id] || ""}
                  onChange={(e) => setVoteNotes((prev) => ({ ...prev, [row.id]: e.target.value }))}
                />
                <button
                  type="button"
                  className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2 hover:bg-accent transition-colors"
                  disabled={busy === `vote-${row.id}-yes`}
                  onClick={() => void vote(row.id, "yes")}
                >
                  {busy === `vote-${row.id}-yes` ? "Saving…" : "Vote YES"}
                </button>
                <button
                  type="button"
                  className="w-full rounded-xl border border-border/40 bg-card/60 px-3 py-2 hover:bg-accent transition-colors"
                  disabled={busy === `vote-${row.id}-no`}
                  onClick={() => void vote(row.id, "no")}
                >
                  {busy === `vote-${row.id}-no` ? "Saving…" : "Vote NO"}
                </button>
              </div>
            </li>
          ))}
          {changeRequests.length === 0 && (
            <li className="text-muted-foreground">{t("contribute.noChangeRequests")}</li>
          )}
        </ul>
      </section>

      <details className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-2 text-sm">
        <summary className="text-xl font-semibold cursor-pointer">{t("contribute.forDevsHeading")}</summary>
        <p className="text-sm text-muted-foreground mt-2">{t("contribute.forDevsBody")}</p>
        <p>{t("contribute.devRegisterContributor")} <code>POST /api/contributors</code></p>
        <p>{t("contribute.devSubmitRequest")} <code>POST /api/governance/change-requests</code></p>
        <p>{t("contribute.devVote")} <code>POST /api/governance/change-requests/&lt;id&gt;/votes</code></p>
        <p>{t("contribute.devListSpecs")}</p>
      </details>

      {status === "loading" && <p className="text-muted-foreground">{t("common.loading")}</p>}
      {status === "error" && <p className="text-destructive">Error: {error}</p>}
      {error && status !== "error" && <p className="text-destructive">Error: {error}</p>}

      {/* Where to go next */}
      <nav className="py-8 text-center space-y-2 border-t border-border/20" aria-label="Where to go next">
        <p className="text-xs text-muted-foreground/80 uppercase tracking-wider">Where to go next</p>
        <div className="flex flex-wrap justify-center gap-4 text-sm">
          <Link href="/ideas" className="text-amber-600 dark:text-amber-400 hover:underline">Ideas</Link>
          <Link href="/specs" className="text-amber-600 dark:text-amber-400 hover:underline">Specs</Link>
          <Link href="/resonance" className="text-amber-600 dark:text-amber-400 hover:underline">Resonance</Link>
        </div>
      </nav>
    </main>
  );
}
