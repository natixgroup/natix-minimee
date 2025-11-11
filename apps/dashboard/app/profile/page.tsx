"use client";

import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { ProfileForm } from "@/components/profile/ProfileForm";
import { SecuritySettings } from "@/components/profile/SecuritySettings";

export default function ProfilePage() {
  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Profile</h1>
          <p className="text-muted-foreground">
            Manage your account settings and preferences
          </p>
        </div>

        <ProfileForm />
        <SecuritySettings />
      </div>
    </DashboardLayout>
  );
}


