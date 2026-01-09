"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  CheckCircle,
  Clock,
  FileText,
  Loader2,
  XCircle,
  Star,
} from "lucide-react";
import type { ResearchPlan, PlanItem } from "@/types";

interface PlanReviewProps {
  plan: ResearchPlan;
  onConfirm: (skipItems: string[]) => void;
  onCancel: () => void;
  isLoading?: boolean;
}

function getPriorityStars(priority: number): string {
  return "★".repeat(6 - priority);
}

function getStatusIcon(status: string) {
  switch (status) {
    case "completed":
      return <CheckCircle className="h-4 w-4 text-green-500" />;
    case "in_progress":
      return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />;
    case "skipped":
      return <XCircle className="h-4 w-4 text-gray-400" />;
    default:
      return <Clock className="h-4 w-4 text-gray-400" />;
  }
}

export function PlanReview({
  plan,
  onConfirm,
  onCancel,
  isLoading = false,
}: PlanReviewProps) {
  const [skippedItems, setSkippedItems] = useState<Set<string>>(new Set());

  const toggleSkip = (itemId: string) => {
    const newSkipped = new Set(skippedItems);
    if (newSkipped.has(itemId)) {
      newSkipped.delete(itemId);
    } else {
      newSkipped.add(itemId);
    }
    setSkippedItems(newSkipped);
  };

  const handleConfirm = () => {
    onConfirm(Array.from(skippedItems));
  };

  const activeItemsCount = plan.plan_items.length - skippedItems.size;

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Research Plan
          </span>
          <Badge variant="secondary">
            ~{plan.estimated_time_minutes} min estimated
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Understanding section */}
        <div className="rounded-lg bg-muted p-4">
          <h4 className="font-medium mb-2">Understanding</h4>
          <p className="text-sm text-muted-foreground">{plan.understanding}</p>
        </div>

        {/* Clarifications if any */}
        {plan.clarifications.length > 0 && (
          <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4">
            <h4 className="font-medium text-yellow-800 mb-2">
              Clarifications Needed
            </h4>
            <ul className="list-disc list-inside text-sm text-yellow-700 space-y-1">
              {plan.clarifications.map((c, i) => (
                <li key={i}>{c}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Plan items */}
        <div>
          <h4 className="font-medium mb-3">
            Research Items ({activeItemsCount} of {plan.plan_items.length}{" "}
            selected)
          </h4>
          <ScrollArea className="h-[400px] rounded-md border p-4">
            <div className="space-y-4">
              {plan.plan_items.map((item, index) => (
                <PlanItemCard
                  key={item.id}
                  item={item}
                  index={index}
                  isSkipped={skippedItems.has(item.id)}
                  onToggleSkip={() => toggleSkip(item.id)}
                />
              ))}
            </div>
          </ScrollArea>
        </div>
      </CardContent>
      <Separator />
      <CardFooter className="flex justify-between pt-4">
        <Button variant="outline" onClick={onCancel} disabled={isLoading}>
          Cancel
        </Button>
        <Button onClick={handleConfirm} disabled={isLoading || activeItemsCount === 0}>
          {isLoading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Starting...
            </>
          ) : (
            <>
              <CheckCircle className="mr-2 h-4 w-4" />
              Confirm & Start Research
            </>
          )}
        </Button>
      </CardFooter>
    </Card>
  );
}

interface PlanItemCardProps {
  item: PlanItem;
  index: number;
  isSkipped: boolean;
  onToggleSkip: () => void;
}

function PlanItemCard({
  item,
  index,
  isSkipped,
  onToggleSkip,
}: PlanItemCardProps) {
  return (
    <div
      className={`rounded-lg border p-4 transition-opacity ${
        isSkipped ? "opacity-50" : ""
      }`}
    >
      <div className="flex items-start gap-3">
        <Checkbox
          checked={!isSkipped}
          onCheckedChange={onToggleSkip}
          className="mt-1"
        />
        <div className="flex-1 space-y-2">
          <div className="flex items-center justify-between">
            <h5 className="font-medium">
              {index + 1}. {item.topic}
            </h5>
            <div className="flex items-center gap-2">
              <span className="text-yellow-500 text-sm">
                {getPriorityStars(item.priority)}
              </span>
              {getStatusIcon(item.status)}
            </div>
          </div>
          <p className="text-sm text-muted-foreground">{item.description}</p>
          {item.scope && (
            <p className="text-xs text-muted-foreground">
              <span className="font-medium">Scope:</span> {item.scope}
            </p>
          )}
          {item.key_questions.length > 0 && (
            <div className="text-xs">
              <span className="font-medium text-muted-foreground">
                Key questions:
              </span>
              <ul className="list-disc list-inside text-muted-foreground mt-1">
                {item.key_questions.slice(0, 3).map((q, i) => (
                  <li key={i}>{q}</li>
                ))}
                {item.key_questions.length > 3 && (
                  <li className="text-primary">
                    +{item.key_questions.length - 3} more
                  </li>
                )}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
