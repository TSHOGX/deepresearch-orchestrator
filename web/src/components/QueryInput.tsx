"use client";

import { useState, FormEvent, KeyboardEvent } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Search, Loader2 } from "lucide-react";

interface QueryInputProps {
  onSubmit: (query: string) => void;
  isLoading?: boolean;
  placeholder?: string;
}

export function QueryInput({
  onSubmit,
  isLoading = false,
  placeholder = "Enter your research question...",
}: QueryInputProps) {
  const [query, setQuery] = useState("");

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (query.trim() && !isLoading) {
      onSubmit(query.trim());
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Submit on Ctrl+Enter or Cmd+Enter
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      if (query.trim() && !isLoading) {
        onSubmit(query.trim());
      }
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Search className="h-5 w-5" />
          Research Query
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <Textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            className="min-h-[120px] resize-none"
            disabled={isLoading}
          />
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              Press <kbd className="rounded bg-muted px-1">Ctrl</kbd>+
              <kbd className="rounded bg-muted px-1">Enter</kbd> to submit
            </p>
            <Button type="submit" disabled={!query.trim() || isLoading}>
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Starting...
                </>
              ) : (
                <>
                  <Search className="mr-2 h-4 w-4" />
                  Start Research
                </>
              )}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
