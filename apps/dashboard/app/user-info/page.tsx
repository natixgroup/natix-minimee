"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { UserInfoCategories } from "@/components/user-info/UserInfoCategories";
import { VisibilityManagementTab } from "@/components/user-info/VisibilityManagementTab";

export default function UserInfoPage() {
  const [userInfos, setUserInfos] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const userId = 1; // TODO: Get from auth context

  useEffect(() => {
    loadUserInfos();
  }, []);

  const loadUserInfos = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getUserInfos(userId);
      setUserInfos(data);
    } catch (err: any) {
      setError(err.message || "Failed to load user information");
    } finally {
      setLoading(false);
    }
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">My Information</h1>
          <p className="text-muted-foreground mt-1">
            Manage your personal information. Click on any field to add or edit in one click. Configure visibility rules for each piece of information.
          </p>
        </div>

        {error && (
          <Card className="border-destructive">
            <CardContent className="pt-6">
              <p className="text-destructive">{error}</p>
            </CardContent>
          </Card>
        )}

        {loading ? (
          <Card>
            <CardContent className="pt-6">
              <p>Loading...</p>
            </CardContent>
          </Card>
        ) : (
          <Tabs defaultValue="information" className="w-full">
            <TabsList>
              <TabsTrigger value="information">My Information</TabsTrigger>
              <TabsTrigger value="visibility">Visibility Rules</TabsTrigger>
            </TabsList>
            <TabsContent value="information" className="mt-6">
              <UserInfoCategories
                userInfos={userInfos}
                userId={userId}
                onUpdate={loadUserInfos}
              />
            </TabsContent>
            <TabsContent value="visibility" className="mt-6">
              <VisibilityManagementTab
                userInfos={userInfos}
                userId={userId}
                onUpdate={loadUserInfos}
              />
            </TabsContent>
          </Tabs>
        )}
      </div>
    </DashboardLayout>
  );
}

