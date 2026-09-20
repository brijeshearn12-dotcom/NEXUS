// Root page — redirects to the Command Center dashboard
import { redirect } from "next/navigation";

export default function Home() {
  redirect("/dashboard");
}
