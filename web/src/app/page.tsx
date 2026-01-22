"use client";

import { useState, useCallback, useEffect } from "react";
import { QueryInput } from "@/components/QueryInput";
import { PlanReview } from "@/components/PlanReview";
import { AgentProgressDisplay } from "@/components/AgentProgress";
import { ReportViewer } from "@/components/ReportViewer";
import { useSSE } from "@/hooks/useSSE";
import {
  startResearch,
  confirmPlan,
  cancelSession,
  getSession,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import {
  AlertCircle,
  CheckCircle,
  Clock,
  FileSearch,
  Loader2,
  RotateCcw,
  XCircle,
} from "lucide-react";
import type {
  ResearchPhase,
  ResearchPlan,
  AgentProgress,
  SSEEvent,
} from "@/types";

type WorkflowStep = "input" | "planning" | "review" | "researching" | "synthesizing" | "complete" | "error" | "cancelled";

interface SessionState {
  sessionId: string | null;
  phase: ResearchPhase | null;
  plan: ResearchPlan | null;
  agentProgress: Record<string, AgentProgress>;
  completedAgents: number;
  totalAgents: number;
  report: string | null;
  error: string | null;
}

const initialState: SessionState = {
  sessionId: null,
  phase: null,
  plan: null,
  agentProgress: {},
  completedAgents: 0,
  totalAgents: 0,
  report: null,
  error: null,
};

function getPhaseLabel(phase: ResearchPhase | null): string {
  switch (phase) {
    case "planning":
      return "Planning";
    case "plan_review":
      return "Plan Review";
    case "researching":
      return "Researching";
    case "synthesizing":
      return "Synthesizing";
    case "completed":
      return "Completed";
    case "failed":
      return "Failed";
    case "cancelled":
      return "Cancelled";
    default:
      return "Starting";
  }
}

function getPhaseIcon(phase: ResearchPhase | null) {
  switch (phase) {
    case "completed":
      return <CheckCircle className="h-4 w-4 text-green-500" />;
    case "failed":
      return <XCircle className="h-4 w-4 text-red-500" />;
    case "cancelled":
      return <AlertCircle className="h-4 w-4 text-gray-500" />;
    default:
      return <Clock className="h-4 w-4 text-blue-500" />;
  }
}

export default function ResearchPage() {
  const [state, setState] = useState<SessionState>(initialState);
  const [isLoading, setIsLoading] = useState(false);
  const [currentStep, setCurrentStep] = useState<WorkflowStep>("input");

  // SSE connection for real-time updates
  const handleSSEEvent = useCallback((event: SSEEvent) => {
    switch (event.event_type) {
      case "plan_draft":
      case "plan_updated":
        if ("plan" in event) {
          setState((prev) => ({
            ...prev,
            plan: event.plan,
            phase: "plan_review",
          }));
          setCurrentStep("review");
        }
        break;

      case "phase_change":
        if ("new_phase" in event) {
          setState((prev) => ({ ...prev, phase: event.new_phase }));
          if (event.new_phase === "researching") {
            setCurrentStep("researching");
          } else if (event.new_phase === "synthesizing") {
            setCurrentStep("synthesizing");
          } else if (event.new_phase === "completed") {
            setCurrentStep("complete");
          } else if (event.new_phase === "failed") {
            setCurrentStep("error");
          } else if (event.new_phase === "cancelled") {
            setCurrentStep("cancelled");
          }
        }
        break;

      case "agent_started":
        if ("agent_id" in event && "topic" in event) {
          setState((prev) => ({
            ...prev,
            agentProgress: {
              ...prev.agentProgress,
              [event.agent_id]: {
                agent_id: event.agent_id,
                plan_item_id: event.plan_item_id || "",
                topic: event.topic,
                status: "running",
                current_action: "Starting...",
                tool_name: null,
                progress_percent: 0,
                started_at: event.timestamp,
                completed_at: null,
                error: null,
              },
            },
          }));
        }
        break;

      case "agent_progress":
        if ("progress" in event) {
          setState((prev) => ({
            ...prev,
            agentProgress: {
              ...prev.agentProgress,
              [event.progress.agent_id]: event.progress,
            },
          }));
        }
        break;

      case "agent_completed":
        if ("result" in event) {
          setState((prev) => ({
            ...prev,
            agentProgress: {
              ...prev.agentProgress,
              [event.result.agent_id]: {
                ...prev.agentProgress[event.result.agent_id],
                status: "completed",
                progress_percent: 100,
              },
            },
            completedAgents: prev.completedAgents + 1,
          }));
        }
        break;

      case "agent_failed":
        if ("agent_id" in event && "error" in event) {
          setState((prev) => ({
            ...prev,
            agentProgress: {
              ...prev.agentProgress,
              [event.agent_id]: {
                ...prev.agentProgress[event.agent_id],
                status: "failed",
                error: event.error,
              },
            },
          }));
        }
        break;

      case "report_ready":
        // Fetch the full report
        if (state.sessionId) {
          getSession(state.sessionId).then((session) => {
            if (session.final_report) {
              setState((prev) => ({
                ...prev,
                report: session.final_report,
              }));
            }
          });
        }
        break;

      case "error":
        if ("error_message" in event) {
          setState((prev) => ({
            ...prev,
            error: event.error_message,
          }));
          setCurrentStep("error");
        }
        break;
    }
  }, [state.sessionId]);

  const { isConnected } = useSSE(state.sessionId, {
    onEvent: handleSSEEvent,
  });

  // Start research
  const handleStartResearch = async (query: string) => {
    setIsLoading(true);
    setCurrentStep("planning");

    try {
      const response = await startResearch({ query });
      setState({
        ...initialState,
        sessionId: response.session_id,
        phase: response.phase,
        plan: response.plan,
        totalAgents: response.total_agents,
      });

      if (response.plan) {
        setCurrentStep("review");
      }
    } catch (error) {
      console.error("Failed to start research:", error);
      setState((prev) => ({
        ...prev,
        error: error instanceof Error ? error.message : "Failed to start research",
      }));
      setCurrentStep("error");
    } finally {
      setIsLoading(false);
    }
  };

  // Confirm plan
  const handleConfirmPlan = async (skipItems: string[]) => {
    if (!state.sessionId) return;

    setIsLoading(true);
    try {
      const response = await confirmPlan(state.sessionId, {
        confirmed: true,
        skip_items: skipItems.length > 0 ? skipItems : undefined,
      });
      setState((prev) => ({
        ...prev,
        phase: response.phase,
        totalAgents: response.total_agents,
      }));
      setCurrentStep("researching");
    } catch (error) {
      console.error("Failed to confirm plan:", error);
      setState((prev) => ({
        ...prev,
        error: error instanceof Error ? error.message : "Failed to confirm plan",
      }));
    } finally {
      setIsLoading(false);
    }
  };

  // Cancel research
  const handleCancel = async () => {
    if (!state.sessionId) {
      setCurrentStep("input");
      setState(initialState);
      return;
    }

    try {
      await cancelSession(state.sessionId);
      setState((prev) => ({ ...prev, phase: "cancelled" }));
      setCurrentStep("cancelled");
    } catch (error) {
      console.error("Failed to cancel:", error);
    }
  };

  // Reset to start new research
  const handleReset = () => {
    setState(initialState);
    setCurrentStep("input");
  };

  // Fetch final report when completed
  useEffect(() => {
    if (state.phase === "completed" && state.sessionId && !state.report) {
      getSession(state.sessionId).then((session) => {
        if (session.final_report) {
          setState((prev) => ({
            ...prev,
            report: session.final_report,
          }));
        }
      });
    }
  }, [state.phase, state.sessionId, state.report]);

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <FileSearch className="h-8 w-8 text-primary" />
              <div>
                <h1 className="text-xl font-bold">Deep Research</h1>
                <p className="text-sm text-muted-foreground">
                  Multi-Agent Research System
                </p>
              </div>
            </div>
            {state.sessionId && (
              <div className="flex items-center gap-3">
                <Badge variant={isConnected ? "default" : "secondary"}>
                  {isConnected ? "Connected" : "Disconnected"}
                </Badge>
                <Badge variant="outline" className="gap-1">
                  {getPhaseIcon(state.phase)}
                  {getPhaseLabel(state.phase)}
                </Badge>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="container mx-auto px-4 py-8">
        <div className="max-w-4xl mx-auto space-y-6">
          {/* Query Input - only show when starting */}
          {currentStep === "input" && (
            <QueryInput
              onSubmit={handleStartResearch}
              isLoading={isLoading}
            />
          )}

          {/* Planning indicator */}
          {currentStep === "planning" && (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-12">
                <Loader2 className="h-12 w-12 animate-spin text-primary mb-4" />
                <h3 className="text-lg font-medium">Creating Research Plan</h3>
                <p className="text-sm text-muted-foreground">
                  Analyzing your query and preparing research strategy...
                </p>
              </CardContent>
            </Card>
          )}

          {/* Plan Review */}
          {currentStep === "review" && state.plan && (
            <PlanReview
              plan={state.plan}
              onConfirm={handleConfirmPlan}
              onCancel={handleCancel}
              isLoading={isLoading}
            />
          )}

          {/* Research Progress */}
          {(currentStep === "researching" || currentStep === "synthesizing") && (
            <>
              <AgentProgressDisplay
                agents={state.agentProgress}
                completedCount={state.completedAgents}
                totalCount={state.totalAgents}
              />
              {currentStep === "synthesizing" && (
                <Card>
                  <CardContent className="flex flex-col items-center justify-center py-8">
                    <Loader2 className="h-8 w-8 animate-spin text-primary mb-3" />
                    <h3 className="text-lg font-medium">Synthesizing Findings</h3>
                    <p className="text-sm text-muted-foreground">
                      Generating comprehensive research report...
                    </p>
                  </CardContent>
                </Card>
              )}
              <div className="flex justify-center">
                <Button variant="outline" onClick={handleCancel}>
                  <XCircle className="h-4 w-4 mr-2" />
                  Cancel Research
                </Button>
              </div>
            </>
          )}

          {/* Report */}
          {currentStep === "complete" && state.report && state.sessionId && (
            <>
              <ReportViewer report={state.report} sessionId={state.sessionId} />
              <div className="flex justify-center">
                <Button onClick={handleReset}>
                  <RotateCcw className="h-4 w-4 mr-2" />
                  Start New Research
                </Button>
              </div>
            </>
          )}

          {/* Error state */}
          {currentStep === "error" && (
            <Card className="border-destructive">
              <CardContent className="flex flex-col items-center justify-center py-12">
                <XCircle className="h-12 w-12 text-destructive mb-4" />
                <h3 className="text-lg font-medium">Research Failed</h3>
                <p className="text-sm text-muted-foreground mb-4">
                  {state.error || "An unexpected error occurred"}
                </p>
                <Button onClick={handleReset}>
                  <RotateCcw className="h-4 w-4 mr-2" />
                  Try Again
                </Button>
              </CardContent>
            </Card>
          )}

          {/* Cancelled state */}
          {currentStep === "cancelled" && (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-12">
                <AlertCircle className="h-12 w-12 text-muted-foreground mb-4" />
                <h3 className="text-lg font-medium">Research Cancelled</h3>
                <p className="text-sm text-muted-foreground mb-4">
                  The research session was cancelled.
                </p>
                <Button onClick={handleReset}>
                  <RotateCcw className="h-4 w-4 mr-2" />
                  Start New Research
                </Button>
              </CardContent>
            </Card>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t mt-auto">
        <div className="container mx-auto px-4 py-4">
          <p className="text-center text-sm text-muted-foreground">
            Powered by Codex CLI &middot; Multi-Agent Deep Research System
          </p>
        </div>
      </footer>
    </div>
  );
}
