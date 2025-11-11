"use client";

import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { X } from "lucide-react";
import { api } from "@/lib/api";

interface RelationType {
  id: number;
  code: string;
  label_masculin: string;
  label_feminin: string;
  label_autre?: string;
  category: string;
  display_order: number;
  is_active: boolean;
  meta_data?: Record<string, any>;
}

interface ContactFormData {
  first_name?: string;
  nickname?: string;
  gender?: string;
  relation_type_ids?: number[];
  context?: string;
  languages?: string[];
  location?: string;
  importance_rating?: number;
  dominant_themes?: string[];
}

interface ContactFormDialogProps {
  open: boolean;
  onClose: () => void;
  onSave: (data: ContactFormData) => Promise<void>;
  initialData?: ContactFormData;
  conversationId: string;
  userId: number;
}

const GENDER_OPTIONS = ["masculin", "féminin", "autre"];

const LANGUAGE_OPTIONS = [
  "français",
  "darija",
  "anglais",
  "espagnol",
  "allemand",
  "italien",
  "portugais",
];

// Helper function to get label based on gender
const getRelationLabel = (relationType: RelationType, gender?: string): string => {
  if (!gender) return relationType.label_autre || relationType.label_masculin;
  switch (gender) {
    case "masculin":
      return relationType.label_masculin;
    case "féminin":
      return relationType.label_feminin;
    default:
      return relationType.label_autre || relationType.label_masculin;
  }
};

export function ContactFormDialog({
  open,
  onClose,
  onSave,
  initialData,
  conversationId,
  userId,
}: ContactFormDialogProps) {
  const [formData, setFormData] = useState<ContactFormData>({
    first_name: "",
    nickname: "",
    gender: "",
    relation_type_ids: [],
    context: "",
    languages: [],
    location: "",
    importance_rating: 3,
    dominant_themes: [],
  });
  const [relationTypes, setRelationTypes] = useState<RelationType[]>([]);
  const [loadingTypes, setLoadingTypes] = useState(false);
  const [themeInput, setThemeInput] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  // Load relation types from API
  useEffect(() => {
    if (open) {
      loadRelationTypes();
    }
  }, [open]);

  const loadRelationTypes = async () => {
    setLoadingTypes(true);
    try {
      const types = await api.getRelationTypes();
      setRelationTypes(types);
    } catch (error) {
      console.error("Error loading relation types:", error);
    } finally {
      setLoadingTypes(false);
    }
  };

  useEffect(() => {
    if (initialData) {
      setFormData({
        first_name: initialData.first_name || "",
        nickname: initialData.nickname || "",
        gender: initialData.gender || "",
        relation_type_ids: initialData.relation_type_ids || [],
        context: initialData.context || "",
        languages: initialData.languages || [],
        location: initialData.location || "",
        importance_rating: initialData.importance_rating || 3,
        dominant_themes: initialData.dominant_themes || [],
      });
    }
  }, [initialData, open]);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await onSave(formData);
      onClose();
    } catch (error) {
      console.error("Error saving contact:", error);
    } finally {
      setIsSaving(false);
    }
  };

  const toggleRelationType = (relationTypeId: number) => {
    const current = formData.relation_type_ids || [];
    if (current.includes(relationTypeId)) {
      setFormData({
        ...formData,
        relation_type_ids: current.filter((id) => id !== relationTypeId),
      });
    } else {
      setFormData({
        ...formData,
        relation_type_ids: [...current, relationTypeId],
      });
    }
  };

  const removeRelationType = (relationTypeId: number) => {
    setFormData({
      ...formData,
      relation_type_ids: formData.relation_type_ids?.filter((id) => id !== relationTypeId) || [],
    });
  };

  const addTheme = () => {
    if (themeInput.trim() && !formData.dominant_themes?.includes(themeInput.trim())) {
      setFormData({
        ...formData,
        dominant_themes: [...(formData.dominant_themes || []), themeInput.trim()],
      });
      setThemeInput("");
    }
  };

  const removeTheme = (theme: string) => {
    setFormData({
      ...formData,
      dominant_themes: formData.dominant_themes?.filter((t) => t !== theme) || [],
    });
  };

  const toggleLanguage = (lang: string) => {
    const current = formData.languages || [];
    if (current.includes(lang)) {
      setFormData({
        ...formData,
        languages: current.filter((l) => l !== lang),
      });
    } else {
      setFormData({
        ...formData,
        languages: [...current, lang],
      });
    }
  };

  // Group relation types by category
  const personnelTypes = relationTypes
    .filter((rt) => rt.category === "personnel" && rt.is_active)
    .sort((a, b) => a.display_order - b.display_order);
  const professionnelTypes = relationTypes
    .filter((rt) => rt.category === "professionnel" && rt.is_active)
    .sort((a, b) => a.display_order - b.display_order);

  // Get selected relation types for display
  const selectedRelationTypes = relationTypes.filter((rt) =>
    formData.relation_type_ids?.includes(rt.id)
  );

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Informations du Contact</DialogTitle>
          <DialogDescription>
            Enrichissez les informations de contact pour améliorer la recherche et le contexte.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div>
            <Label htmlFor="gender">Sexe</Label>
            <Select
              value={formData.gender}
              onValueChange={(value) =>
                setFormData({ ...formData, gender: value })
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="Sélectionner le sexe" />
              </SelectTrigger>
              <SelectContent>
                {GENDER_OPTIONS.map((gender) => (
                  <SelectItem key={gender} value={gender}>
                    {gender}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="first_name">Prénom</Label>
              <Input
                id="first_name"
                value={formData.first_name}
                onChange={(e) =>
                  setFormData({ ...formData, first_name: e.target.value })
                }
                placeholder="Prénom"
              />
            </div>
            <div>
              <Label htmlFor="nickname">Petit nom</Label>
              <Input
                id="nickname"
                value={formData.nickname}
                onChange={(e) =>
                  setFormData({ ...formData, nickname: e.target.value })
                }
                placeholder="Surnom"
              />
            </div>
          </div>

          <div>
            <Label>Types de relation</Label>
            {loadingTypes ? (
              <div className="text-sm text-muted-foreground mt-2">Chargement...</div>
            ) : (
              <>
                {selectedRelationTypes.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-2 mb-3">
                    {selectedRelationTypes.map((rt) => (
                      <Badge
                        key={rt.id}
                        variant="secondary"
                        className="gap-1 cursor-pointer"
                        onClick={() => removeRelationType(rt.id)}
                      >
                        {getRelationLabel(rt, formData.gender)}
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            removeRelationType(rt.id);
                          }}
                          className="ml-1 hover:bg-destructive/20 rounded-full p-0.5"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </Badge>
                    ))}
                  </div>
                )}
                <Tabs defaultValue="personnel" className="mt-2">
                  <TabsList className="grid w-full grid-cols-2">
                    <TabsTrigger value="personnel">Personnel</TabsTrigger>
                    <TabsTrigger value="professionnel">Professionnel</TabsTrigger>
                  </TabsList>
                  <TabsContent value="personnel" className="mt-3">
                    <div className="flex flex-wrap gap-2">
                      {personnelTypes.map((rt) => {
                        const isSelected = formData.relation_type_ids?.includes(rt.id);
                        return (
                          <Button
                            key={rt.id}
                            type="button"
                            variant={isSelected ? "default" : "outline"}
                            size="sm"
                            onClick={() => toggleRelationType(rt.id)}
                            disabled={!formData.gender}
                          >
                            {getRelationLabel(rt, formData.gender)}
                          </Button>
                        );
                      })}
                    </div>
                    {!formData.gender && (
                      <p className="text-xs text-muted-foreground mt-2">
                        Sélectionnez d'abord le sexe pour voir les relations
                      </p>
                    )}
                  </TabsContent>
                  <TabsContent value="professionnel" className="mt-3">
                    <div className="flex flex-wrap gap-2">
                      {professionnelTypes.map((rt) => {
                        const isSelected = formData.relation_type_ids?.includes(rt.id);
                        return (
                          <Button
                            key={rt.id}
                            type="button"
                            variant={isSelected ? "default" : "outline"}
                            size="sm"
                            onClick={() => toggleRelationType(rt.id)}
                          >
                            {getRelationLabel(rt, formData.gender)}
                          </Button>
                        );
                      })}
                    </div>
                  </TabsContent>
                </Tabs>
              </>
            )}
          </div>

          <div>
            <Label htmlFor="context">Contexte</Label>
            <Textarea
              id="context"
              value={formData.context}
              onChange={(e) =>
                setFormData({ ...formData, context: e.target.value })
              }
              placeholder="Contexte de la relation..."
              rows={3}
            />
          </div>

          <div>
            <Label>Langues</Label>
            <div className="flex flex-wrap gap-2 mt-2">
              {LANGUAGE_OPTIONS.map((lang) => (
                <Button
                  key={lang}
                  type="button"
                  variant={
                    formData.languages?.includes(lang) ? "default" : "outline"
                  }
                  size="sm"
                  onClick={() => toggleLanguage(lang)}
                >
                  {lang}
                </Button>
              ))}
            </div>
          </div>

          <div>
            <Label htmlFor="location">Localisation</Label>
            <Input
              id="location"
              value={formData.location}
              onChange={(e) =>
                setFormData({ ...formData, location: e.target.value })
              }
              placeholder="Ville, Pays"
            />
          </div>

          <div>
            <Label>
              Importance relationnelle: {formData.importance_rating}/5
            </Label>
            <Slider
              value={[formData.importance_rating || 3]}
              onValueChange={([value]) =>
                setFormData({ ...formData, importance_rating: value })
              }
              min={1}
              max={5}
              step={1}
              className="mt-2"
            />
          </div>

          <div>
            <Label>Thèmes dominants</Label>
            <div className="flex gap-2 mt-2">
              <Input
                value={themeInput}
                onChange={(e) => setThemeInput(e.target.value)}
                onKeyPress={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addTheme();
                  }
                }}
                placeholder="Ajouter un thème"
              />
              <Button type="button" onClick={addTheme} size="sm">
                Ajouter
              </Button>
            </div>
            <div className="flex flex-wrap gap-2 mt-2">
              {formData.dominant_themes?.map((theme) => (
                <Badge key={theme} variant="secondary" className="gap-1">
                  {theme}
                  <button
                    type="button"
                    onClick={() => removeTheme(theme)}
                    className="ml-1 hover:bg-destructive/20 rounded-full p-0.5"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isSaving}>
            Annuler
          </Button>
          <Button onClick={handleSave} disabled={isSaving}>
            {isSaving ? "Enregistrement..." : "Enregistrer"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
