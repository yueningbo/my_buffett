export type Verdict = "pass" | "concern" | "veto";

export interface ReviewVerdict {
  principle_id: string;
  verdict: Verdict;
  rationale: string;
  missing_info: string[];
  evidence_refs: string[];
}

export interface ReviewResult {
  symbol: string;
  name: string | null;
  items: ReviewVerdict[];
  overall: Verdict;
  summary: string;
  evidence_refs: string[];
}

export interface ThesisCard {
  symbol: string;
  name: string | null;
  thesis: string;
  key_assumptions: string[];
  open_questions: string[];
  last_review: ReviewResult | null;
  todos: string[];
  updated_at: string;
}

export interface ChatResponse {
  reply: string;
  mode: "broad" | "company";
  symbol: string | null;
  tool_calls: string[];
  review: ReviewResult | null;
  thesis: ThesisCard | null;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  mode?: "broad" | "company";
}
