"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  FileText,
  Download,
  Copy,
  Check,
  ExternalLink,
} from "lucide-react";

interface ReportViewerProps {
  report: string;
  sessionId: string;
}

export function ReportViewer({ report, sessionId }: ReportViewerProps) {
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState("preview");

  const handleCopy = async () => {
    await navigator.clipboard.writeText(report);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const blob = new Blob([report], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `research_report_${sessionId.slice(0, 8)}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-green-500" />
            Research Report
          </span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={handleCopy}>
              {copied ? (
                <>
                  <Check className="h-4 w-4 mr-1" />
                  Copied
                </>
              ) : (
                <>
                  <Copy className="h-4 w-4 mr-1" />
                  Copy
                </>
              )}
            </Button>
            <Button variant="outline" size="sm" onClick={handleDownload}>
              <Download className="h-4 w-4 mr-1" />
              Download
            </Button>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="preview">Preview</TabsTrigger>
            <TabsTrigger value="source">Source</TabsTrigger>
          </TabsList>
          <TabsContent value="preview">
            <ScrollArea className="h-[600px] rounded-md border p-6">
              <div className="prose prose-sm max-w-none dark:prose-invert">
                <ReactMarkdown
                  components={{
                    h1: ({ children }) => (
                      <h1 className="text-2xl font-bold mt-6 mb-4 pb-2 border-b">
                        {children}
                      </h1>
                    ),
                    h2: ({ children }) => (
                      <h2 className="text-xl font-semibold mt-5 mb-3">
                        {children}
                      </h2>
                    ),
                    h3: ({ children }) => (
                      <h3 className="text-lg font-medium mt-4 mb-2">
                        {children}
                      </h3>
                    ),
                    p: ({ children }) => (
                      <p className="mb-4 leading-relaxed">{children}</p>
                    ),
                    ul: ({ children }) => (
                      <ul className="list-disc list-inside mb-4 space-y-1">
                        {children}
                      </ul>
                    ),
                    ol: ({ children }) => (
                      <ol className="list-decimal list-inside mb-4 space-y-1">
                        {children}
                      </ol>
                    ),
                    li: ({ children }) => (
                      <li className="text-muted-foreground">{children}</li>
                    ),
                    blockquote: ({ children }) => (
                      <blockquote className="border-l-4 border-primary pl-4 italic my-4 text-muted-foreground">
                        {children}
                      </blockquote>
                    ),
                    code: ({ className, children, ...props }) => {
                      const isInline = !className;
                      if (isInline) {
                        return (
                          <code className="bg-muted px-1.5 py-0.5 rounded text-sm font-mono">
                            {children}
                          </code>
                        );
                      }
                      return (
                        <code
                          className="block bg-muted p-4 rounded-md overflow-x-auto text-sm font-mono"
                          {...props}
                        >
                          {children}
                        </code>
                      );
                    },
                    a: ({ href, children }) => (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary hover:underline inline-flex items-center gap-1"
                      >
                        {children}
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    ),
                    table: ({ children }) => (
                      <div className="overflow-x-auto my-4">
                        <table className="min-w-full divide-y divide-border">
                          {children}
                        </table>
                      </div>
                    ),
                    th: ({ children }) => (
                      <th className="px-4 py-2 text-left font-medium bg-muted">
                        {children}
                      </th>
                    ),
                    td: ({ children }) => (
                      <td className="px-4 py-2 border-t">{children}</td>
                    ),
                  }}
                >
                  {report}
                </ReactMarkdown>
              </div>
            </ScrollArea>
          </TabsContent>
          <TabsContent value="source">
            <ScrollArea className="h-[600px] rounded-md border">
              <pre className="p-4 text-sm font-mono whitespace-pre-wrap">
                {report}
              </pre>
            </ScrollArea>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
