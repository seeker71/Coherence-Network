import { redirect } from "next/navigation";

// /usage consolidated into /pipeline.
// Runtime cost, provider health, and daily summaries are now at /pipeline.
export default function UsageRedirect() {
  redirect("/pipeline");
}
