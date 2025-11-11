"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Edit, Trash2, Eye } from "lucide-react";
import { VisibilityManager } from "./VisibilityManager";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface UserInfoTableProps {
  userInfos: any[];
  userId: number;
  onEdit: (userInfo: any) => void;
  onDelete: (userInfoId: number) => void;
  onReload: () => void;
}

export function UserInfoTable({
  userInfos,
  userId,
  onEdit,
  onDelete,
  onReload,
}: UserInfoTableProps) {
  const [visibilities, setVisibilities] = useState<Record<number, any[]>>({});
  const [loadingVisibilities, setLoadingVisibilities] = useState<Record<number, boolean>>({});
  const [selectedUserInfo, setSelectedUserInfo] = useState<any | null>(null);
  const [isVisibilityDialogOpen, setIsVisibilityDialogOpen] = useState(false);

  useEffect(() => {
    // Load visibilities for all user infos
    userInfos.forEach((userInfo) => {
      loadVisibilities(userInfo.id);
    });
  }, [userInfos]);

  const loadVisibilities = async (userInfoId: number) => {
    try {
      setLoadingVisibilities((prev) => ({ ...prev, [userInfoId]: true }));
      const data = await api.getUserInfoVisibilities(userInfoId, userId);
      setVisibilities((prev) => ({ ...prev, [userInfoId]: data }));
    } catch (err) {
      console.error("Failed to load visibilities:", err);
    } finally {
      setLoadingVisibilities((prev) => ({ ...prev, [userInfoId]: false }));
    }
  };

  const handleManageVisibility = (userInfo: any) => {
    setSelectedUserInfo(userInfo);
    setIsVisibilityDialogOpen(true);
  };

  const formatInfoType = (type: string) => {
    return type
      .split("_")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  };

  const formatInfoValue = (userInfo: any) => {
    if (userInfo.info_value_json) {
      if (Array.isArray(userInfo.info_value_json)) {
        return userInfo.info_value_json.join(", ");
      }
      return JSON.stringify(userInfo.info_value_json);
    }
    return userInfo.info_value || "";
  };

  const getVisibilitySummary = (userInfoId: number) => {
    const vis = visibilities[userInfoId] || [];
    if (vis.length === 0) return "No rules";
    
    const canUse = vis.filter((v) => v.can_use_for_response).length;
    const canSay = vis.filter((v) => v.can_say_explicitly).length;
    const forbidden = vis.filter((v) => v.forbidden_for_response || v.forbidden_to_say).length;
    
    return `${canUse} can use, ${canSay} can say, ${forbidden} forbidden`;
  };

  if (userInfos.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        No user information found. Click "Add Information" to get started.
      </div>
    );
  }

  return (
    <>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Type</TableHead>
              <TableHead>Value</TableHead>
              <TableHead>Visibility Rules</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {userInfos.map((userInfo) => (
              <TableRow key={userInfo.id}>
                <TableCell className="font-medium">
                  {formatInfoType(userInfo.info_type)}
                </TableCell>
                <TableCell>
                  <div className="max-w-md truncate" title={formatInfoValue(userInfo)}>
                    {formatInfoValue(userInfo)}
                  </div>
                </TableCell>
                <TableCell>
                  <Badge variant="outline" className="text-xs">
                    {loadingVisibilities[userInfo.id] ? (
                      "Loading..."
                    ) : (
                      getVisibilitySummary(userInfo.id)
                    )}
                  </Badge>
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex justify-end gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleManageVisibility(userInfo)}
                      title="Manage visibility"
                    >
                      <Eye className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onEdit(userInfo)}
                      title="Edit"
                    >
                      <Edit className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onDelete(userInfo.id)}
                      title="Delete"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <Dialog open={isVisibilityDialogOpen} onOpenChange={setIsVisibilityDialogOpen}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Manage Visibility Rules</DialogTitle>
            <DialogDescription>
              Control who can see and use this information
            </DialogDescription>
          </DialogHeader>
          {selectedUserInfo && (
            <VisibilityManager
              userInfo={selectedUserInfo}
              userId={userId}
              visibilities={visibilities[selectedUserInfo.id] || []}
              onReload={() => {
                loadVisibilities(selectedUserInfo.id);
                onReload();
              }}
            />
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}


