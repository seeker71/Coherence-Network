import { redirect } from "next/navigation";

// /usage has been consolidated into /pipeline
// Runtime telemetry, provider performance, and task execution info is now on the Pipeline page.
export default function UsageRedirect() {
  redirect("/pipeline");
}
