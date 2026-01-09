"use client";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Bot,
  CheckCircle,
  Clock,
  Loader2,
  XCircle,
  AlertCircle,
} from "lucide-react";
import type { AgentProgress as AgentProgressType, AgentStatus } from "@/types";

interface AgentProgressProps {
  agents: Record<string, AgentProgressType>;
  completedCount: number;
  totalCount: number;
}

function getStatusBadge(status: AgentStatus) {
  switch (status) {
    case "completed":
      return (
        <Badge variant="success" className="gap-1">
          <CheckCircle className="h-3 w-3" />
          Completed
        </Badge>
      );
    case "running":
      return (
        <Badge variant="default" className="gap-1">
          <Loader2 className="h-3 w-3 animate-spin" />
          Running
        </Badge>
      );
    case "failed":
      return (
        <Badge variant="destructive" className="gap-1">
          <XCircle className="h-3 w-3" />
          Failed
        </Badge>
      );
    case "cancelled":
      return (
        <Badge variant="secondary" className="gap-1">
          <AlertCircle className="h-3 w-3" />
          Cancelled
        </Badge>
      );
    default:
      return (
        <Badge variant="outline" className="gap-1">
          <Clock className="h-3 w-3" />
          Pending
        </Badge>
      );
  }
}

export function AgentProgressDisplay({
  agents,
  completedCount,
  totalCount,
}: AgentProgressProps) {
  const agentList = Object.values(agents);
  const overallProgress = totalCount > 0 ? (completedCount / totalCount) * 100 : 0;

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span className="flex items-center gap-2">
            <Bot className="h-5 w-5" />
            Research Progress
          </span>
          <Badge variant="secondary">
            {completedCount} / {totalCount} completed
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Overall progress */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Overall Progress</span>
            <span className="font-medium">{Math.round(overallProgress)}%</span>
          </div>
          <Progress value={overallProgress} className="h-3" />
        </div>

        {/* Agent list */}
        <ScrollArea className="h-[400px] rounded-md border">
          <div className="p-4 space-y-4">
            {agentList.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <Bot className="h-12 w-12 mx-auto mb-3 opacity-50" />
                <p>Waiting for agents to start...</p>
              </div>
            ) : (
              agentList.map((agent) => (
                <AgentCard key={agent.agent_id} agent={agent} />
              ))
            )}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}

interface AgentCardProps {
  agent: AgentProgressType;
}

function AgentCard({ agent }: AgentCardProps) {
  const isActive = agent.status === "running";

  return (
    <div
      className={`rounded-lg border p-4 space-y-3 ${
        isActive ? "border-primary bg-primary/5" : ""
      }`}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <h4 className="font-medium text-sm">{agent.topic}</h4>
          {agent.current_action && (
            <p className="text-xs text-muted-foreground mt-1 truncate max-w-[300px]">
              {agent.current_action}
            </p>
          )}
        </div>
        {getStatusBadge(agent.status)}
      </div>

      <div className="space-y-1">
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>
            {agent.tool_name ? `Using: ${agent.tool_name}` : "Processing..."}
          </span>
          <span>{Math.round(agent.progress_percent)}%</span>
        </div>
        <Progress value={agent.progress_percent} className="h-2" />
      </div>

      {agent.error && (
        <div className="text-xs text-destructive bg-destructive/10 rounded p-2">
          {agent.error}
        </div>
      )}
    </div>
  );
}
