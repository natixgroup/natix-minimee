"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Loader2, CheckCircle2 } from "lucide-react";

interface GettingToKnowSessionProps {
  sessionId: number;
  userId: number;
  onComplete: () => void;
}

export function GettingToKnowSession({
  sessionId,
  userId,
  onComplete,
}: GettingToKnowSessionProps) {
  const [currentQuestion, setCurrentQuestion] = useState<any | null>(null);
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadQuestion();
  }, [sessionId]);

  const loadQuestion = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getCurrentQuestion(sessionId, userId);
      setCurrentQuestion(data);
      if (data.completed) {
        onComplete();
      }
    } catch (err: any) {
      setError(err.message || "Failed to load question");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!answer.trim() || submitting) return;

    try {
      setSubmitting(true);
      setError(null);
      const data = await api.answerGettingToKnowQuestion(
        sessionId,
        userId,
        answer.trim(),
        currentQuestion?.question_type
      );
      
      setAnswer("");
      setCurrentQuestion(data);
      
      if (data.completed) {
        onComplete();
      }
    } catch (err: any) {
      setError(err.message || "Failed to submit answer");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="border-destructive">
        <CardContent className="pt-6">
          <p className="text-destructive">{error}</p>
        </CardContent>
      </Card>
    );
  }

  if (currentQuestion?.completed) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="text-center py-8">
            <CheckCircle2 className="h-12 w-12 mx-auto mb-4 text-green-500" />
            <h3 className="text-lg font-semibold mb-2">Session Complete!</h3>
            <p className="text-muted-foreground">{currentQuestion.message}</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  const progress = currentQuestion?.progress;
  const progressPercent = progress
    ? Math.round((progress.answered / progress.total) * 100)
    : 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Getting to Know You</CardTitle>
        {progress && (
          <div className="space-y-2 mt-4">
            <div className="flex justify-between text-sm">
              <span>Progress</span>
              <span>
                {progress.answered} / {progress.total} questions
              </span>
            </div>
            <Progress value={progressPercent} />
          </div>
        )}
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="answer" className="text-base">
              {currentQuestion?.question}
            </Label>
            {currentQuestion?.required && (
              <span className="text-destructive ml-1">*</span>
            )}
            <Input
              id="answer"
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder="Your answer..."
              required={currentQuestion?.required}
              disabled={submitting}
              autoFocus
            />
          </div>

          {error && (
            <div className="text-sm text-destructive">{error}</div>
          )}

          <div className="flex justify-end gap-2">
            <Button
              type="submit"
              disabled={!answer.trim() || submitting}
            >
              {submitting ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Submitting...
                </>
              ) : (
                "Next"
              )}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}


