import { redirect } from "next/navigation";

// /automation consolidated into /nodes (infrastructure) and /pipeline (execution).
// Provider stats and exec health live at /pipeline.
export default function AutomationRedirect() {
  redirect("/pipeline");
}
