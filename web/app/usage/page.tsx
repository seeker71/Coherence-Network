import { redirect } from "next/navigation";

// /usage has been consolidated into /pipeline
// All task execution stats, provider performance, and daily summaries are at /pipeline
export default function UsagePage() {
  redirect("/pipeline");
}
