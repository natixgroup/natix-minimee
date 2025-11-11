"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Plus, Trash2, Linkedin } from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface Education {
  id: string;
  institution: string;
  degree: string;
  field: string;
  startDate: string;
  endDate: string;
  description: string;
}

interface EducationInputProps {
  educations: Education[];
  onChange: (educations: Education[]) => void;
  onLinkedInImport?: () => void;
}

export function EducationInput({ educations, onChange, onLinkedInImport }: EducationInputProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [isAdding, setIsAdding] = useState(false);
  const [formData, setFormData] = useState<Partial<Education>>({
    institution: "",
    degree: "",
    field: "",
    startDate: "",
    endDate: "",
    description: "",
  });

  const handleSave = () => {
    if (editingId) {
      onChange(educations.map((e) => (e.id === editingId ? { ...e, ...formData } as Education : e)));
      setEditingId(null);
    } else {
      onChange([
        ...educations,
        {
          id: Date.now().toString(),
          institution: formData.institution || "",
          degree: formData.degree || "",
          field: formData.field || "",
          startDate: formData.startDate || "",
          endDate: formData.endDate || "",
          description: formData.description || "",
        },
      ]);
      setIsAdding(false);
    }
    setFormData({
      institution: "",
      degree: "",
      field: "",
      startDate: "",
      endDate: "",
      description: "",
    });
  };

  const handleEdit = (education: Education) => {
    setEditingId(education.id);
    setFormData(education);
    setIsAdding(false);
  };

  const handleDelete = (id: string) => {
    onChange(educations.filter((e) => e.id !== id));
  };

  return (
    <div className="space-y-3">
      {educations.map((education) => (
        <div key={education.id} className="border rounded-lg p-4 space-y-2">
          {editingId === education.id ? (
            <EducationForm
              data={formData}
              onChange={setFormData}
              onSave={handleSave}
              onCancel={() => {
                setEditingId(null);
                setFormData({
                  institution: "",
                  degree: "",
                  field: "",
                  startDate: "",
                  endDate: "",
                  description: "",
                });
              }}
            />
          ) : (
            <>
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="font-semibold">{education.degree}</div>
                  <div className="text-sm text-muted-foreground">{education.institution}</div>
                  {education.field && (
                    <Badge variant="outline" className="mt-1">
                      {education.field}
                    </Badge>
                  )}
                  {education.startDate && education.endDate && (
                    <div className="text-xs text-muted-foreground mt-1">
                      {education.startDate} - {education.endDate}
                    </div>
                  )}
                  {education.description && (
                    <div className="text-sm mt-2">{education.description}</div>
                  )}
                </div>
                <div className="flex gap-2">
                  <Button variant="ghost" size="sm" onClick={() => handleEdit(education)}>
                    Edit
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDelete(education.id)}
                    className="text-destructive"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </>
          )}
        </div>
      ))}

      {isAdding ? (
        <div className="border-2 border-dashed rounded-lg p-4">
          <EducationForm
            data={formData}
            onChange={setFormData}
            onSave={handleSave}
            onCancel={() => {
              setIsAdding(false);
              setFormData({
                institution: "",
                degree: "",
                field: "",
                startDate: "",
                endDate: "",
                description: "",
              });
            }}
          />
        </div>
      ) : (
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setIsAdding(true)} className="flex-1">
            <Plus className="h-4 w-4 mr-2" />
            Add Education
          </Button>
          {onLinkedInImport && (
            <Button variant="outline" onClick={onLinkedInImport}>
              <Linkedin className="h-4 w-4 mr-2" />
              Import from LinkedIn
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

function EducationForm({
  data,
  onChange,
  onSave,
  onCancel,
}: {
  data: Partial<Education>;
  onChange: (data: Partial<Education>) => void;
  onSave: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2">
        <Input
          placeholder="Institution"
          value={data.institution || ""}
          onChange={(e) => onChange({ ...data, institution: e.target.value })}
        />
        <Input
          placeholder="Degree"
          value={data.degree || ""}
          onChange={(e) => onChange({ ...data, degree: e.target.value })}
        />
      </div>
      <Input
        placeholder="Field of study"
        value={data.field || ""}
        onChange={(e) => onChange({ ...data, field: e.target.value })}
      />
      <div className="grid grid-cols-2 gap-2">
        <Input
          placeholder="Start date (YYYY)"
          value={data.startDate || ""}
          onChange={(e) => onChange({ ...data, startDate: e.target.value })}
        />
        <Input
          placeholder="End date (YYYY)"
          value={data.endDate || ""}
          onChange={(e) => onChange({ ...data, endDate: e.target.value })}
        />
      </div>
      <Textarea
        placeholder="Description (optional)"
        value={data.description || ""}
        onChange={(e) => onChange({ ...data, description: e.target.value })}
        rows={2}
      />
      <div className="flex gap-2">
        <Button onClick={onSave} size="sm">
          Save
        </Button>
        <Button variant="outline" onClick={onCancel} size="sm">
          Cancel
        </Button>
      </div>
    </div>
  );
}


