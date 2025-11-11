"use client";

import { useState, useMemo, useEffect, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Plus, Edit2, X, Check, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { getEnv } from "@/lib/env";
import { toast } from "sonner";
import { DateInput } from "./DateInput";
import { PhoneInput } from "./PhoneInput";
import { EmailInput } from "./EmailInput";
import { AddressInput } from "./AddressInput";
import { EducationInput } from "./EducationInput";
import { SelectInput } from "./SelectInput";
import { VisibilityRulesInline } from "./VisibilityRulesInline";

interface UserInfo {
  id: number;
  info_type: string;
  info_value: string | null;
  info_value_json: any;
}

interface UserInfoCategoriesProps {
  userInfos: UserInfo[];
  userId: number;
  onUpdate: () => void;
}

const GENDER_OPTIONS = [
  { value: "male", label: "Male" },
  { value: "female", label: "Female" },
  { value: "non-binary", label: "Non-binary" },
  { value: "prefer-not-to-say", label: "Prefer not to say" },
  { value: "other", label: "Other" },
];

const MARITAL_STATUS_OPTIONS = [
  { value: "single", label: "Single" },
  { value: "married", label: "Married" },
  { value: "divorced", label: "Divorced" },
  { value: "widowed", label: "Widowed" },
  { value: "separated", label: "Separated" },
  { value: "domestic-partnership", label: "Domestic Partnership" },
  { value: "civil-union", label: "Civil Union" },
];

const INFO_CATEGORIES = {
  identity: {
    label: "Identity",
    icon: "👤",
    types: [
      { value: "first_name", label: "First Name", component: "text" },
      { value: "last_name", label: "Last Name", component: "text" },
      { value: "birth_date", label: "Date of Birth", component: "date" },
      { value: "gender", label: "Gender", component: "select", options: GENDER_OPTIONS },
      { value: "phone", label: "Phone Numbers", component: "phone" },
      { value: "email", label: "Email Addresses", component: "email" },
    ],
  },
  location: {
    label: "Location",
    icon: "📍",
    types: [
      { value: "address", label: "Addresses", component: "address" },
      { value: "city", label: "City", component: "text" },
      { value: "country", label: "Country", component: "text" },
      { value: "timezone", label: "Timezone", component: "text" },
    ],
  },
  professional: {
    label: "Professional",
    icon: "💼",
    types: [
      { value: "profession", label: "Profession", component: "text" },
      { value: "company", label: "Company", component: "text" },
      { value: "job_title", label: "Job Title", component: "text" },
      { value: "education", label: "Education", component: "education" },
      { value: "skills", label: "Skills", component: "tags" },
    ],
  },
  personal: {
    label: "Personal",
    icon: "👨‍👩‍👧",
    types: [
      { value: "marital_status", label: "Marital Status", component: "select", options: MARITAL_STATUS_OPTIONS },
      { value: "partner", label: "Partner", component: "text" },
      { value: "children", label: "Children", component: "tags" },
      { value: "family_members", label: "Family Members", component: "tags" },
    ],
  },
  preferences: {
    label: "Preferences",
    icon: "⭐",
    types: [
      { value: "languages", label: "Languages", component: "tags" },
      { value: "communication_style", label: "Communication Style", component: "text" },
      { value: "preferred_emojis", label: "Preferred Emojis", component: "tags" },
      { value: "humor_style", label: "Humor Style", component: "text" },
      { value: "response_tone", label: "Response Tone", component: "text" },
    ],
  },
  likes: {
    label: "What I Like",
    icon: "❤️",
    types: [
      { value: "likes_food", label: "Food", component: "tags" },
      { value: "likes_music", label: "Music", component: "tags" },
      { value: "likes_movies", label: "Movies", component: "tags" },
      { value: "likes_books", label: "Books", component: "tags" },
      { value: "likes_sports", label: "Sports", component: "tags" },
      { value: "likes_hobbies", label: "Hobbies", component: "tags" },
      { value: "likes_activities", label: "Activities", component: "tags" },
      { value: "likes_places", label: "Places", component: "tags" },
      { value: "likes_colors", label: "Colors", component: "tags" },
    ],
  },
  dislikes: {
    label: "What I Dislike",
    icon: "🚫",
    types: [
      { value: "dislikes_food", label: "Food", component: "tags" },
      { value: "dislikes_activities", label: "Activities", component: "tags" },
      { value: "dislikes_topics", label: "Topics to Avoid", component: "tags" },
      { value: "dislikes_behaviors", label: "Behaviors", component: "tags" },
    ],
  },
  values: {
    label: "Values & Beliefs",
    icon: "💭",
    types: [
      { value: "values", label: "Values", component: "tags" },
      { value: "beliefs", label: "Beliefs", component: "text" },
      { value: "priorities", label: "Priorities", component: "tags" },
      { value: "goals", label: "Goals", component: "tags" },
    ],
  },
  health: {
    label: "Health & Wellness",
    icon: "🏥",
    types: [
      { value: "health_conditions", label: "Health Conditions", component: "tags" },
      { value: "dietary_restrictions", label: "Dietary Restrictions", component: "tags" },
      { value: "fitness_level", label: "Fitness Level", component: "text" },
      { value: "sleep_schedule", label: "Sleep Schedule", component: "text" },
    ],
  },
};

export function UserInfoCategories({
  userInfos,
  userId,
  onUpdate,
}: UserInfoCategoriesProps) {
  // Use Map-based state to avoid shared state bug
  const [editingValues, setEditingValues] = useState<Map<number, string>>(new Map());
  const [addingValues, setAddingValues] = useState<Map<string, string>>(new Map());
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  // Track modifications and success animations
  const [showSuccessAnimation, setShowSuccessAnimation] = useState<Map<number, boolean>>(new Map());
  const [showValidationButton, setShowValidationButton] = useState<Map<number, boolean>>(new Map());
  const inputRefs = useRef<Map<number, HTMLInputElement | null>>(new Map());
  
  // Tag input states
  const [tagInputValues, setTagInputValues] = useState<Map<number, string>>(new Map());
  const [removingTagIndices, setRemovingTagIndices] = useState<Map<number, number | null>>(new Map());

  // Get Google Places API key for address autocomplete (using REST API, no script loading needed)
  const { googlePlacesApiKey } = getEnv();

  const getUserInfoByType = (type: string): UserInfo | undefined => {
    return userInfos.find((info) => info.info_type === type);
  };

  const formatValue = (userInfo: UserInfo): string => {
    if (userInfo.info_value_json) {
      if (Array.isArray(userInfo.info_value_json)) {
        return userInfo.info_value_json.join(", ");
      }
      return JSON.stringify(userInfo.info_value_json);
    }
    return userInfo.info_value || "";
  };

  const parseValue = (value: string, isArray: boolean = false) => {
    if (isArray) {
      const items = value.split(",").map((item) => item.trim()).filter(Boolean);
      return {
        info_value: items.join(", "),
        info_value_json: items,
      };
    }
    return { info_value: value };
  };

  const handleSave = async (userInfoId: number, data: any) => {
    setIsSubmitting(true);
    try {
      await api.updateUserInfo(userInfoId, userId, data);
      // Clear editing state for this field
      setEditingValues((prev) => {
        const next = new Map(prev);
        next.delete(userInfoId);
        return next;
      });
      // Hide validation button
      setShowValidationButton((prev) => {
        const next = new Map(prev);
        next.delete(userInfoId);
        return next;
      });
      // Trigger success animation
      setShowSuccessAnimation((prev) => {
        const next = new Map(prev);
        next.set(userInfoId, true);
        return next;
      });
      // Clear animation after 2.5 seconds
      setTimeout(() => {
        setShowSuccessAnimation((prev) => {
          const next = new Map(prev);
          next.delete(userInfoId);
          return next;
        });
      }, 2500);
      toast.success("Information updated successfully");
      onUpdate();
    } catch (err: any) {
      let errorMessage = "Error saving";
      if (err instanceof Error) {
        errorMessage = err.message || "Error saving";
      } else if (typeof err === "string") {
        errorMessage = err;
      } else if (err && typeof err === "object") {
        // Try to extract message from various possible error formats
        if (err.message && typeof err.message === "string") {
          errorMessage = err.message;
        } else if (err.error && typeof err.error === "string") {
          errorMessage = err.error;
        } else if (err.detail && typeof err.detail === "string") {
          errorMessage = err.detail;
        } else if (err.response?.data?.detail) {
          errorMessage = String(err.response.data.detail);
        } else if (err.response?.data?.message) {
          errorMessage = String(err.response.data.message);
        } else {
          // Last resort: try to stringify, but limit length
          try {
            const str = JSON.stringify(err);
            errorMessage = str.length > 100 ? str.substring(0, 100) + "..." : str;
          } catch {
            errorMessage = "Error saving (unknown error format)";
          }
        }
      }
      // Ensure errorMessage is always a string
      const finalErrorMessage = typeof errorMessage === "string" ? errorMessage : String(errorMessage);
      toast.error(finalErrorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCreate = async (type: string, data: any) => {
    setIsSubmitting(true);
    try {
      await api.createUserInfo(userId, { info_type: type, ...data });
      // Clear adding state for this field type
      setAddingValues((prev) => {
        const next = new Map(prev);
        next.delete(type);
        return next;
      });
      toast.success("Information added successfully");
      onUpdate();
    } catch (err: any) {
      let errorMessage = "Error creating";
      if (err instanceof Error) {
        errorMessage = err.message || "Error creating";
      } else if (typeof err === "string") {
        errorMessage = err;
      } else if (err && typeof err === "object") {
        // Try to extract message from various possible error formats
        if (err.message && typeof err.message === "string") {
          errorMessage = err.message;
        } else if (err.error && typeof err.error === "string") {
          errorMessage = err.error;
        } else if (err.detail && typeof err.detail === "string") {
          errorMessage = err.detail;
        } else if (err.response?.data?.detail) {
          errorMessage = String(err.response.data.detail);
        } else if (err.response?.data?.message) {
          errorMessage = String(err.response.data.message);
        } else {
          // Last resort: try to stringify, but limit length
          try {
            const str = JSON.stringify(err);
            errorMessage = str.length > 100 ? str.substring(0, 100) + "..." : str;
          } catch {
            errorMessage = "Error creating (unknown error format)";
          }
        }
      }
      // Ensure errorMessage is always a string
      const finalErrorMessage = typeof errorMessage === "string" ? errorMessage : String(errorMessage);
      toast.error(finalErrorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (userInfoId: number) => {
    if (!confirm("Are you sure you want to delete this information?")) {
      return;
    }
    try {
      await api.deleteUserInfo(userInfoId, userId);
      toast.success("Information deleted successfully");
      onUpdate();
    } catch (err: any) {
      let errorMessage = "Error deleting";
      if (err instanceof Error) {
        errorMessage = err.message || "Error deleting";
      } else if (typeof err === "string") {
        errorMessage = err;
      } else if (err && typeof err === "object") {
        // Try to extract message from various possible error formats
        if (err.message && typeof err.message === "string") {
          errorMessage = err.message;
        } else if (err.error && typeof err.error === "string") {
          errorMessage = err.error;
        } else if (err.detail && typeof err.detail === "string") {
          errorMessage = err.detail;
        } else if (err.response?.data?.detail) {
          errorMessage = String(err.response.data.detail);
        } else if (err.response?.data?.message) {
          errorMessage = String(err.response.data.message);
        } else {
          // Last resort: try to stringify, but limit length
          try {
            const str = JSON.stringify(err);
            errorMessage = str.length > 100 ? str.substring(0, 100) + "..." : str;
          } catch {
            errorMessage = "Error deleting (unknown error format)";
          }
        }
      }
      // Ensure errorMessage is always a string
      const finalErrorMessage = typeof errorMessage === "string" ? errorMessage : String(errorMessage);
      toast.error(finalErrorMessage);
    }
  };

  const renderField = (typeConfig: any, userInfo?: UserInfo) => {
    const { value, label, component, options } = typeConfig;
    const currentEditingValue = userInfo ? editingValues.get(userInfo.id) : undefined;
    const currentAddingValue = addingValues.get(value) || "";

    if (component === "phone") {
      // Convert old format {id, number, tags: [{id, label}]} to new format {id, number, tags: string[]}
      const phonesRaw = userInfo?.info_value_json || [];
      const phones = phonesRaw.map((p: any) => ({
        id: p.id || String(Date.now() + Math.random()),
        number: p.number || p,
        tags: Array.isArray(p.tags)
          ? p.tags.map((t: any) => (typeof t === "string" ? t : t.label || t.id))
          : [],
      }));
      return (
        <div className="space-y-2">
          <div className="flex items-center justify-between mb-2">
            <label className="text-sm font-medium">{label}</label>
            {userInfo && (
              <>
                <VisibilityRulesInline userInfoId={userInfo.id} userId={userId} onUpdate={onUpdate} />
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleDelete(userInfo.id)}
                  className="h-7 w-7 p-0"
                >
                  <Trash2 className="h-3 w-3 text-destructive" />
                </Button>
              </>
            )}
          </div>
          <PhoneInput
            phones={phones}
            onChange={async (newPhones) => {
              if (userInfo) {
                await handleSave(userInfo.id, {
                  info_value: newPhones.map((p) => p.number).join(", "),
                  info_value_json: newPhones,
                });
              } else if (newPhones.length > 0) {
                await handleCreate(value, {
                  info_value: newPhones.map((p) => p.number).join(", "),
                  info_value_json: newPhones,
                });
              }
            }}
          />
        </div>
      );
    }

    if (component === "email") {
      // Convert old format {id, address, tags: [{id, label}]} to new format {id, address, tags: string[]}
      const emailsRaw = userInfo?.info_value_json || [];
      const emails = emailsRaw.map((e: any) => ({
        id: e.id || String(Date.now() + Math.random()),
        address: e.address || e,
        tags: Array.isArray(e.tags)
          ? e.tags.map((t: any) => (typeof t === "string" ? t : t.label || t.id))
          : [],
      }));
      return (
        <div className="space-y-2">
          <div className="flex items-center justify-between mb-2">
            <label className="text-sm font-medium">{label}</label>
            {userInfo && (
              <>
                <VisibilityRulesInline userInfoId={userInfo.id} userId={userId} onUpdate={onUpdate} />
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleDelete(userInfo.id)}
                  className="h-7 w-7 p-0"
                >
                  <Trash2 className="h-3 w-3 text-destructive" />
                </Button>
              </>
            )}
          </div>
          <EmailInput
            emails={emails}
            onChange={async (newEmails) => {
              if (userInfo) {
                await handleSave(userInfo.id, {
                  info_value: newEmails.map((e) => e.address).join(", "),
                  info_value_json: newEmails,
                });
              } else if (newEmails.length > 0) {
                await handleCreate(value, {
                  info_value: newEmails.map((e) => e.address).join(", "),
                  info_value_json: newEmails,
                });
              }
            }}
          />
        </div>
      );
    }

    if (component === "address") {
      // Convert old format {id, address, tags: [{id, label}]} to new format {id, address, tags: string[]}
      const addressesRaw = userInfo?.info_value_json || [];
      const addresses = addressesRaw.map((a: any) => ({
        id: a.id || String(Date.now() + Math.random()),
        address: a.address || a,
        tags: Array.isArray(a.tags)
          ? a.tags.map((t: any) => (typeof t === "string" ? t : t.label || t.id))
          : [],
        isCurrent: a.isCurrent || false,
      }));
      return (
        <div className="space-y-2">
          <div className="flex items-center justify-between mb-2">
            <label className="text-sm font-medium">{label}</label>
            {userInfo && (
              <>
                <VisibilityRulesInline userInfoId={userInfo.id} userId={userId} onUpdate={onUpdate} />
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleDelete(userInfo.id)}
                  className="h-7 w-7 p-0"
                >
                  <Trash2 className="h-3 w-3 text-destructive" />
                </Button>
              </>
            )}
          </div>
          <AddressInput
            addresses={addresses}
            googleApiKey={googlePlacesApiKey}
            onChange={async (newAddresses) => {
              if (userInfo) {
                await handleSave(userInfo.id, {
                  info_value: newAddresses.map((a) => a.address).join("; "),
                  info_value_json: newAddresses,
                });
              } else if (newAddresses.length > 0) {
                await handleCreate(value, {
                  info_value: newAddresses.map((a) => a.address).join("; "),
                  info_value_json: newAddresses,
                });
              }
            }}
          />
        </div>
      );
    }

    if (component === "date") {
      return (
        <div className="space-y-2">
          <div className="flex items-center justify-between mb-2">
            <label className="text-sm font-medium">{label}</label>
            {userInfo && (
              <>
                <VisibilityRulesInline userInfoId={userInfo.id} userId={userId} onUpdate={onUpdate} />
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleDelete(userInfo.id)}
                  className="h-7 w-7 p-0"
                >
                  <Trash2 className="h-3 w-3 text-destructive" />
                </Button>
              </>
            )}
          </div>
          {userInfo ? (
            <DateInput
              value={userInfo.info_value || ""}
              onChange={async (newValue) => {
                await handleSave(userInfo.id, { info_value: newValue });
              }}
            />
          ) : (
            <div className="flex gap-2">
              <DateInput
                value={currentAddingValue}
                onChange={(newValue) => {
                  setAddingValues((prev) => new Map(prev).set(value, newValue));
                }}
                placeholder="DD/MM/YYYY"
              />
              <Button
                onClick={() => handleCreate(value, { info_value: currentAddingValue })}
                disabled={!currentAddingValue.trim() || isSubmitting}
                size="sm"
              >
                <Check className="h-4 w-4 mr-1" />
                Add
              </Button>
            </div>
          )}
        </div>
      );
    }

    if (component === "select") {
      const selected = userInfo?.info_value_json || (userInfo?.info_value ? [userInfo.info_value] : []);
      return (
        <div className="space-y-2">
          <div className="flex items-center justify-between mb-2">
            <label className="text-sm font-medium">{label}</label>
            {userInfo && (
              <>
                <VisibilityRulesInline userInfoId={userInfo.id} userId={userId} onUpdate={onUpdate} />
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleDelete(userInfo.id)}
                  className="h-7 w-7 p-0"
                >
                  <Trash2 className="h-3 w-3 text-destructive" />
                </Button>
              </>
            )}
          </div>
          {userInfo ? (
            <SelectInput
              options={options || []}
              selected={selected}
              onChange={async (newSelected) => {
                try {
                  await handleSave(userInfo.id, {
                    info_value: newSelected.join(", "),
                    info_value_json: newSelected,
                  });
                } catch (err) {
                  // Error is already handled in handleSave with toast
                  console.error("Error saving select value:", err);
                }
              }}
              multiple={true}
            />
          ) : (
            <SelectInput
              options={options || []}
              selected={[]}
              onChange={async (newSelected) => {
                try {
                  await handleCreate(value, {
                    info_value: newSelected.join(", "),
                    info_value_json: newSelected,
                  });
                } catch (err) {
                  // Error is already handled in handleCreate with toast
                  console.error("Error creating select value:", err);
                }
              }}
              multiple={true}
            />
          )}
        </div>
      );
    }

    if (component === "tags") {
      const tags = userInfo?.info_value_json || [];
      const tagInputValue = userInfo ? (tagInputValues.get(userInfo.id) || "") : "";
      const removingTagIndex = userInfo ? (removingTagIndices.get(userInfo.id) ?? null) : null;

      const handleRemoveTag = async (tagIndex: number) => {
        if (!userInfo) return;
        setRemovingTagIndices((prev) => {
          const next = new Map(prev);
          next.set(userInfo.id, tagIndex);
          return next;
        });
        // Animation delay
        setTimeout(() => {
          const newTags = tags.filter((_: string, idx: number) => idx !== tagIndex);
          handleSave(userInfo.id, {
            info_value: newTags.join(", "),
            info_value_json: newTags,
          });
          setRemovingTagIndices((prev) => {
            const next = new Map(prev);
            next.delete(userInfo.id);
            return next;
          });
        }, 200);
      };

      const handleAddTag = async (tagValue: string) => {
        if (!userInfo) return;
        if (tagValue.trim() && !tags.includes(tagValue.trim())) {
          const newTags = [...tags, tagValue.trim()];
          await handleSave(userInfo.id, {
            info_value: newTags.join(", "),
            info_value_json: newTags,
          });
          setTagInputValues((prev) => {
            const next = new Map(prev);
            next.delete(userInfo.id);
            return next;
          });
        }
      };

      return (
        <div className="space-y-2">
          <div className="flex items-center justify-between mb-2">
            <label className="text-sm font-medium">{label}</label>
            {userInfo && (
              <>
                <VisibilityRulesInline userInfoId={userInfo.id} userId={userId} onUpdate={onUpdate} />
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleDelete(userInfo.id)}
                  className="h-7 w-7 p-0"
                >
                  <Trash2 className="h-3 w-3 text-destructive" />
                </Button>
              </>
            )}
          </div>
          {userInfo ? (
            <div className="space-y-2">
              <div className="flex flex-wrap gap-2 min-h-[32px] p-2 border rounded-md">
                {tags.map((tag: string, idx: number) => (
                  <Badge
                    key={idx}
                    variant="secondary"
                    className={`group cursor-pointer transition-all duration-200 ${
                      removingTagIndex === idx ? "opacity-0 scale-90" : "opacity-100 scale-100"
                    }`}
                    onClick={() => handleRemoveTag(idx)}
                  >
                    {tag}
                    <X className="h-3 w-3 ml-1 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </Badge>
                ))}
                <Input
                  placeholder={tags.length === 0 ? "Type and press Enter or Space to add tags" : ""}
                  value={tagInputValue}
                  onChange={(e) => {
                    if (userInfo) {
                      setTagInputValues((prev) => new Map(prev).set(userInfo.id, e.target.value));
                    }
                  }}
                  onKeyDown={async (e) => {
                    if ((e.key === "Enter" || e.key === " ") && tagInputValue.trim()) {
                      e.preventDefault();
                      await handleAddTag(tagInputValue);
                    }
                  }}
                  className="border-0 focus-visible:ring-0 h-auto p-0 flex-1 min-w-[120px]"
                />
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              <Input
                placeholder="Type and press Enter or Space to add tags"
                value={currentAddingValue}
                onChange={(e) => {
                  setAddingValues((prev) => new Map(prev).set(value, e.target.value));
                }}
                onKeyDown={async (e) => {
                  if ((e.key === "Enter" || e.key === " ") && currentAddingValue.trim()) {
                    e.preventDefault();
                    const tags = currentAddingValue.split(/[,\s]+/).map((t) => t.trim()).filter(Boolean);
                    if (tags.length > 0) {
                      await handleCreate(value, {
                        info_value: tags.join(", "),
                        info_value_json: tags,
                      });
                    }
                  }
                }}
              />
            </div>
          )}
        </div>
      );
    }

    if (component === "education") {
      const educations = userInfo?.info_value_json || [];
      return (
        <div className="space-y-2">
          <div className="flex items-center justify-between mb-2">
            <label className="text-sm font-medium">{label}</label>
            {userInfo && (
              <VisibilityRulesInline userInfoId={userInfo.id} userId={userId} onUpdate={onUpdate} />
            )}
          </div>
          <EducationInput
            educations={educations}
            onChange={async (newEducations) => {
              if (userInfo) {
                await handleSave(userInfo.id, {
                  info_value: newEducations.map((e) => `${e.degree} at ${e.institution}`).join("; "),
                  info_value_json: newEducations,
                });
              } else {
                await handleCreate(value, {
                  info_value: newEducations.map((e) => `${e.degree} at ${e.institution}`).join("; "),
                  info_value_json: newEducations,
                });
              }
            }}
            onLinkedInImport={async () => {
              // TODO: Implement LinkedIn OAuth import
              toast.info("LinkedIn import coming soon!");
            }}
          />
        </div>
      );
    }

    // Default text input
    return (
      <div className="space-y-2">
        <div className="flex items-center justify-between mb-2">
          <label className="text-sm font-medium">{label}</label>
          {userInfo && (
            <>
              <VisibilityRulesInline userInfoId={userInfo.id} userId={userId} onUpdate={onUpdate} />
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleDelete(userInfo.id)}
                className="h-7 w-7 p-0"
              >
                <Trash2 className="h-3 w-3 text-destructive" />
              </Button>
            </>
          )}
        </div>
        {userInfo ? (
          <div className="relative">
            <div className="flex gap-2 items-center">
              <div className="relative flex-1">
                <Input
                  ref={(el) => {
                    if (el) inputRefs.current.set(userInfo.id, el);
                  }}
                  value={currentEditingValue !== undefined ? currentEditingValue : (userInfo.info_value || "")}
                  onChange={(e) => {
                    const newValue = e.target.value;
                    setEditingValues((prev) => new Map(prev).set(userInfo.id, newValue));
                    // Show validation button if value changed
                    const originalValue = userInfo.info_value || "";
                    if (newValue !== originalValue) {
                      setShowValidationButton((prev) => {
                        const next = new Map(prev);
                        next.set(userInfo.id, true);
                        return next;
                      });
                    } else {
                      setShowValidationButton((prev) => {
                        const next = new Map(prev);
                        next.delete(userInfo.id);
                        return next;
                      });
                    }
                  }}
                  onKeyDown={async (e) => {
                    if (e.key === "Enter" && showValidationButton.get(userInfo.id)) {
                      e.preventDefault();
                      const valueToSave = currentEditingValue !== undefined ? currentEditingValue : userInfo.info_value;
                      await handleSave(userInfo.id, { info_value: valueToSave || "" });
                    } else if (e.key === "Escape") {
                      setEditingValues((prev) => {
                        const next = new Map(prev);
                        next.delete(userInfo.id);
                        return next;
                      });
                      setShowValidationButton((prev) => {
                        const next = new Map(prev);
                        next.delete(userInfo.id);
                        return next;
                      });
                    }
                  }}
                  onBlur={() => {
                    // Don't auto-save on blur anymore, user must click validation button
                    if (currentEditingValue === undefined || currentEditingValue === userInfo.info_value) {
                      setEditingValues((prev) => {
                        const next = new Map(prev);
                        next.delete(userInfo.id);
                        return next;
                      });
                      setShowValidationButton((prev) => {
                        const next = new Map(prev);
                        next.delete(userInfo.id);
                        return next;
                      });
                    }
                  }}
                  className={`flex-1 transition-all duration-500 ${
                    showSuccessAnimation.get(userInfo.id)
                      ? "border-green-500 bg-green-50 dark:bg-green-950 shadow-[0_0_0_2px_rgba(34,197,94,0.2)]"
                      : ""
                  }`}
                />
                {/* Success checkmark overlay */}
                {showSuccessAnimation.get(userInfo.id) && (
                  <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none animate-fade-out">
                    <Check className="h-5 w-5 text-green-600 dark:text-green-400" />
                  </div>
                )}
              </div>
              {/* Validation button */}
              {showValidationButton.get(userInfo.id) && (
                <Button
                  onClick={async () => {
                    const valueToSave = currentEditingValue !== undefined ? currentEditingValue : userInfo.info_value;
                    await handleSave(userInfo.id, { info_value: valueToSave || "" });
                  }}
                  size="sm"
                  className="shrink-0"
                >
                  <Check className="h-4 w-4 mr-1" />
                  Save
                </Button>
              )}
            </div>
          </div>
        ) : (
          <div className="flex gap-2">
            <Input
              value={currentAddingValue}
              onChange={(e) => {
                setAddingValues((prev) => new Map(prev).set(value, e.target.value));
              }}
              placeholder={`Enter ${label.toLowerCase()}`}
              onKeyDown={async (e) => {
                if (e.key === "Enter" && currentAddingValue.trim()) {
                  await handleCreate(value, { info_value: currentAddingValue });
                }
              }}
              className="flex-1"
            />
            <Button
              onClick={() => handleCreate(value, { info_value: currentAddingValue })}
              disabled={!currentAddingValue.trim() || isSubmitting}
              size="sm"
            >
              <Check className="h-4 w-4 mr-1" />
              Add
            </Button>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-8">
      {Object.entries(INFO_CATEGORIES).map(([categoryKey, category]) => (
        <Card key={categoryKey}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <span className="text-2xl">{category.icon}</span>
              {category.label}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {category.types.map((type) => {
                const userInfo = getUserInfoByType(type.value);
                return (
                  <div key={type.value} className="border rounded-lg p-4 space-y-2">
                    {renderField(type, userInfo)}
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
