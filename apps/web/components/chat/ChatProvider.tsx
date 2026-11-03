"use client";

import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import { ApiError, askQuestion } from "@/lib/api";
import type { AnswerMode, QueryResponse, Retrieval } from "@/lib/types";

export type Turn = {
  id: number;
  question: string;
  mode: AnswerMode;
  retrieval: Retrieval;
  status: "pending" | "done" | "error" | "stopped";
  response?: QueryResponse;
  error?: string;
};

type Selection = { turnId: number; citationId: string } | null;

type ChatContextValue = {
  turns: Turn[];
  activeTurn: Turn | undefined;
  selection: Selection;
  pending: boolean;
  lastQuestion: string | null;
  ask: (question: string, mode: AnswerMode, retrieval: Retrieval) => Promise<void>;
  stop: () => void;
  clear: () => void;
  drawerOpen: boolean;
  setDrawerOpen: (open: boolean) => void;
  selectCitation: (turnId: number, citationId: string) => void;
  selectTurn: (turnId: number) => void;
};

const ChatContext = createContext<ChatContextValue | null>(null);

export function useChat(): ChatContextValue {
  const value = useContext(ChatContext);
  if (!value) throw new Error("useChat must be used inside <ChatProvider>");
  return value;
}

export const MIN_QUESTION = 3;
export const MAX_QUESTION = 550;

let turnCounter = 0;

export function ChatProvider({ children }: { children: React.ReactNode }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [selection, setSelection] = useState<Selection>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const controller = useRef<AbortController | null>(null);

  const pending = turns.some((t) => t.status === "pending");

  const patch = useCallback((id: number, change: Partial<Turn>) => {
    setTurns((all) => all.map((t) => (t.id === id ? { ...t, ...change } : t)));
  }, []);

  const ask = useCallback(
    async (rawQuestion: string, mode: AnswerMode, retrieval: Retrieval) => {
      const question = rawQuestion.trim();
      if (question.length < MIN_QUESTION || question.length > MAX_QUESTION || controller.current) return;

      const id = ++turnCounter;
      const abort = new AbortController();
      controller.current = abort;
      setTurns((all) => [...all, { id, question, mode, retrieval, status: "pending" }]);
      setActiveId(id);
      setSelection(null);
      try {
        const response = await askQuestion(question, mode, retrieval, abort.signal);
        patch(id, { status: "done", response });
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") {
          patch(id, { status: "stopped" });
        } else {
          patch(id, { status: "error", error: err instanceof ApiError ? err.message : "Something went wrong." });
        }
      } finally {
        controller.current = null;
      }
    },
    [patch],
  );

  const stop = useCallback(() => controller.current?.abort(), []);

  const clear = useCallback(() => {
    controller.current?.abort();
    setTurns([]);
    setActiveId(null);
    setSelection(null);
    setDrawerOpen(false);
  }, []);

  const selectTurn = useCallback((turnId: number) => {
    setActiveId(turnId);
    setSelection(null);
  }, []);

  const selectCitation = useCallback((turnId: number, citationId: string) => {
    setActiveId(turnId);
    setSelection({ turnId, citationId });
  }, []);

  const value = useMemo<ChatContextValue>(() => {
    const activeTurn = turns.find((t) => t.id === activeId) ?? turns[turns.length - 1];
    return {
      turns,
      activeTurn,
      selection,
      pending,
      lastQuestion: turns.length ? turns[turns.length - 1].question : null,
      ask,
      stop,
      clear,
      drawerOpen,
      setDrawerOpen,
      selectCitation,
      selectTurn,
    };
  }, [turns, activeId, selection, pending, drawerOpen, ask, stop, clear, selectCitation, selectTurn]);

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}
