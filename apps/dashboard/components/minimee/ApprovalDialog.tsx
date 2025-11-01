"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Loader2, CheckCircle2, XCircle, AlertCircle } from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";

export interface MessageOptions {
  message_id: number;
  conversation_id?: string;
  options: string[];
}

interface ApprovalDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  messageOptions: MessageOptions | null;
  onApproved?: (optionIndex: number) => void;
  onRejected?: () => void;
  type?: "whatsapp_message" | "email_draft";
  emailThreadId?: string;
}

export function ApprovalDialog({
  open,
  onOpenChange,
  messageOptions,
  onApproved,
  onRejected,
  type = "whatsapp_message",
  emailThreadId,
}: ApprovalDialogProps) {
  const [selectedOption, setSelectedOption] = useState<number | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  if (!messageOptions || !messageOptions.options || messageOptions.options.length === 0) {
    return null;
  }

  const optionLabels = ["A", "B", "C"];

  const handleApprove = async (optionIndex: number) => {
    if (!messageOptions) return;

    setIsProcessing(true);
    try {
      const response = await api.approveMessage(
        messageOptions.message_id,
        optionIndex,
        "yes",
        type,
        emailThreadId
      );

      if (response.status === "approved") {
        toast.success("Response approved and sent!");
        onApproved?.(optionIndex);
        onOpenChange(false);
      } else {
        toast.error(response.message || "Approval failed");
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to approve message");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleReject = async () => {
    if (!messageOptions) return;

    setIsProcessing(true);
    try {
      await api.approveMessage(
        messageOptions.message_id,
        0,
        "no",
        type,
        emailThreadId
      );
      toast.info("Response rejected");
      onRejected?.();
      onOpenChange(false);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to reject message");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleSelectOption = (index: number) => {
    setSelectedOption(index);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {type === "email_draft" ? "📧 Email Draft Options" : "💬 Response Options"}
          </DialogTitle>
          <DialogDescription>
            {type === "email_draft"
              ? "Select an email draft option to send, or reject all"
              : "Review the generated response options and select one to send, or reject all"}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {messageOptions.options.map((option, index) => (
            <Card
              key={index}
              className={`cursor-pointer transition-all ${
                selectedOption === index
                  ? "ring-2 ring-primary border-primary"
                  : "hover:border-primary/50"
              }`}
              onClick={() => handleSelectOption(index)}
            >
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg flex items-center gap-2">
                    <Badge variant="outline" className="font-mono text-lg">
                      {optionLabels[index] || `${index + 1}`}
                    </Badge>
                    Option {optionLabels[index] || `${index + 1}`}
                  </CardTitle>
                  {selectedOption === index && (
                    <CheckCircle2 className="h-5 w-5 text-primary" />
                  )}
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-sm whitespace-pre-wrap">{option}</p>
              </CardContent>
            </Card>
          ))}
        </div>

        <DialogFooter className="flex gap-2">
          <Button
            variant="outline"
            onClick={handleReject}
            disabled={isProcessing}
          >
            {isProcessing ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <XCircle className="mr-2 h-4 w-4" />
            )}
            Reject All
          </Button>
          <Button
            onClick={() => selectedOption !== null && handleApprove(selectedOption)}
            disabled={selectedOption === null || isProcessing}
          >
            {isProcessing ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <CheckCircle2 className="mr-2 h-4 w-4" />
            )}
            {selectedOption !== null
              ? `Approve Option ${optionLabels[selectedOption] || selectedOption + 1}`
              : "Select an option"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

