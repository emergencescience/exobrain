import type { Metadata } from "next";
import ExobrainClient from "@/components/ExobrainClient";

export const metadata: Metadata = {
  title: "Exobrain — AI STEM Paper Editor",
  description:
    "Build your academic paper through natural language conversation. AI-powered Markdown + LaTeX paper editor.",
};

export default function Home() {
  return <ExobrainClient lang="en" />;
}
