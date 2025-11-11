"use client";

import { useState, useEffect, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Plus, Search, X } from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { CategoryButtons } from "./CategoryButtons";

interface UserInfo {
  id: number;
  info_type: string;
  info_value: string | null;
  info_value_json: any;
}

interface Contact {
  id: number;
  conversation_id: string;
  first_name?: string;
  nickname?: string;
  contact_category_id?: number;
}

interface ContactCategory {
  id: number;
  code: string;
  label: string;
  category_type: string;
}

type VisibilityLevel = "full" | "context_only" | "hidden";

interface VisibilityRule {
  user_info_id: number;
  relation_type_id: number | null;
  contact_id: number | null;
  level: VisibilityLevel;
}

const LEVEL_LABELS: Record<VisibilityLevel, { label: string; color: string; emoji: string }> = {
  full: { label: "Full Access", color: "bg-green-500", emoji: "🟢" },
  context_only: { label: "Context Only", color: "bg-blue-500", emoji: "🔵" },
  hidden: { label: "Hidden", color: "bg-red-500", emoji: "🔴" },
};

interface VisibilityManagementTabProps {
  userInfos: UserInfo[];
  userId: number;
  onUpdate: () => void;
}

export function VisibilityManagementTab({
  userInfos,
  userId,
  onUpdate,
}: VisibilityManagementTabProps) {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [categories, setCategories] = useState<ContactCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [visibilityRules, setVisibilityRules] = useState<Map<string, VisibilityRule>>(new Map());

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [contactsData, categoriesData] = await Promise.all([
        api.getAllContacts(userId),
        api.getContactCategories(userId),
      ]);
      setContacts(contactsData);
      setCategories(categoriesData);
      
      // Load visibility rules for all user infos
      await loadVisibilityRules();
    } catch (err: any) {
      const errorMessage = err instanceof Error ? err.message : String(err?.message || "Failed to load data");
      toast.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const loadVisibilityRules = async () => {
    const rulesMap = new Map<string, VisibilityRule>();
    
    for (const userInfo of userInfos) {
      try {
        const visibilities = await api.getUserInfoVisibilities(userInfo.id, userId);
        
        // Default rule
        const defaultRule = visibilities.find(
          (v: any) => v.relation_type_id === null && v.contact_id === null
        );
        if (defaultRule) {
          const level = flagsToLevel(defaultRule);
          rulesMap.set(`${userInfo.id}-default`, {
            user_info_id: userInfo.id,
            relation_type_id: null,
            contact_id: null,
            level,
          });
        }
        
        // Note: ContactCategory rules would need a new field contact_category_id in UserInfoVisibility
        // For now, we'll handle individual contacts only
        // Category-based rules can be added later when backend supports it
        
        // Contact rules
        for (const contact of contacts) {
          const contactRule = visibilities.find((v: any) => v.contact_id === contact.id);
          if (contactRule) {
            const level = flagsToLevel(contactRule);
            rulesMap.set(`${userInfo.id}-contact-${contact.id}`, {
              user_info_id: userInfo.id,
              relation_type_id: null,
              contact_id: contact.id,
              level,
            });
          }
        }
      } catch (err) {
        console.error(`Failed to load visibility for info ${userInfo.id}:`, err);
      }
    }
    
    setVisibilityRules(rulesMap);
  };

  const flagsToLevel = (rule: any): VisibilityLevel => {
    if (rule.forbidden_for_response || rule.forbidden_to_say) {
      return "hidden";
    }
    if (rule.can_use_for_response && rule.can_say_explicitly) {
      return "full";
    }
    if (rule.can_use_for_response && !rule.can_say_explicitly) {
      return "context_only";
    }
    return "hidden";
  };

  const levelToFlags = (level: VisibilityLevel) => {
    switch (level) {
      case "full":
        return {
          can_use_for_response: true,
          can_say_explicitly: true,
          forbidden_for_response: false,
          forbidden_to_say: false,
        };
      case "context_only":
        return {
          can_use_for_response: true,
          can_say_explicitly: false,
          forbidden_for_response: false,
          forbidden_to_say: false,
        };
      case "hidden":
        return {
          can_use_for_response: false,
          can_say_explicitly: false,
          forbidden_for_response: true,
          forbidden_to_say: true,
        };
    }
  };

  const handleUpdateLevel = async (
    userInfoId: number,
    level: VisibilityLevel,
    contactId?: number
  ) => {
    try {
      const flags = levelToFlags(level);
      const key = contactId
        ? `${userInfoId}-contact-${contactId}`
        : `${userInfoId}-default`;

      // Find existing rule
      const visibilities = await api.getUserInfoVisibilities(userInfoId, userId);
      const existingRule = visibilities.find(
        (v: any) =>
          v.relation_type_id === null &&
          v.contact_id === (contactId || null)
      );

      if (existingRule) {
        await api.updateUserInfoVisibility(userInfoId, existingRule.id, userId, flags);
      } else {
        await api.createUserInfoVisibility(userInfoId, userId, {
          relation_type_id: null,
          contact_id: contactId || null,
          ...flags,
        });
      }

      // Update local state
      setVisibilityRules((prev) => {
        const next = new Map(prev);
        next.set(key, {
          user_info_id: userInfoId,
          relation_type_id: null,
          contact_id: contactId || null,
          level,
        });
        return next;
      });

      onUpdate();
    } catch (err: any) {
      const errorMessage = err instanceof Error ? err.message : String(err?.message || "Failed to update visibility");
      toast.error(errorMessage);
    }
  };

  const getLevel = (userInfoId: number, contactId?: number): VisibilityLevel => {
    const key = contactId
      ? `${userInfoId}-contact-${contactId}`
      : `${userInfoId}-default`;
    return visibilityRules.get(key)?.level || "context_only";
  };

  const filteredContacts = useMemo(() => {
    if (!searchQuery.trim()) return contacts;
    const query = searchQuery.toLowerCase();
    return contacts.filter(
      (c) =>
        c.first_name?.toLowerCase().includes(query) ||
        c.nickname?.toLowerCase().includes(query) ||
        c.conversation_id.toLowerCase().includes(query)
    );
  }, [contacts, searchQuery]);

  const getInfoLabel = (infoType: string) => {
    return infoType
      .split("_")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  };

  if (loading) {
    return <div className="text-center py-8">Loading...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Visibility Rules</h2>
          <p className="text-muted-foreground text-sm mt-1">
            Manage who can see and use each piece of information
          </p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Matrix View</CardTitle>
            <div className="flex items-center gap-2">
              <div className="relative">
                <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search contacts..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-8 w-64"
                />
              </div>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr>
                  <th className="border p-2 text-left font-medium sticky left-0 bg-background z-10">
                    Information
                  </th>
                  <th className="border p-2 text-left font-medium min-w-[120px]">
                    Default
                  </th>
                  {/* Categories will be added when backend supports contact_category_id in UserInfoVisibility */}
                  {filteredContacts.map((contact) => (
                    <th key={contact.id} className="border p-2 text-left font-medium min-w-[150px]">
                      <div className="text-xs">
                        {contact.first_name || contact.nickname || "Unknown"}
                        {contact.conversation_id && (
                          <div className="text-muted-foreground text-[10px] mt-0.5">
                            {contact.conversation_id}
                          </div>
                        )}
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {userInfos.map((userInfo) => {
                  const defaultLevel = getLevel(userInfo.id);
                  return (
                    <tr key={userInfo.id}>
                      <td className="border p-2 sticky left-0 bg-background z-10 font-medium">
                        {getInfoLabel(userInfo.info_type)}
                      </td>
                      <td className="border p-2">
                        <CategoryButtons
                          categories={["Full Access", "Context Only", "Hidden"]}
                          selected={[LEVEL_LABELS[defaultLevel].label]}
                          onChange={(selected) => {
                            const level = Object.entries(LEVEL_LABELS).find(
                              ([_, info]) => info.label === selected[0]
                            )?.[0] as VisibilityLevel;
                            if (level) {
                              handleUpdateLevel(userInfo.id, level);
                            }
                          }}
                        />
                      </td>
                      {/* Category columns will be added when backend supports contact_category_id in UserInfoVisibility */}
                      {filteredContacts.map((contact) => {
                        const level = getLevel(userInfo.id, contact.id);
                        return (
                          <td key={contact.id} className="border p-2">
                            <CategoryButtons
                              categories={["Full Access", "Context Only", "Hidden"]}
                              selected={[LEVEL_LABELS[level].label]}
                              onChange={(selected) => {
                                const newLevel = Object.entries(LEVEL_LABELS).find(
                                  ([_, info]) => info.label === selected[0]
                                )?.[0] as VisibilityLevel;
                                if (newLevel) {
                                  handleUpdateLevel(userInfo.id, newLevel, contact.id);
                                }
                              }}
                            />
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

