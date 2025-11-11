"use client";

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, Trash2, MapPin } from "lucide-react";
import { CategoryButtons } from "./CategoryButtons";
import { Badge } from "@/components/ui/badge";

interface Address {
  id: string;
  address: string;
  tags: string[];
  isCurrent: boolean;
}

interface AddressInputProps {
  addresses: Address[];
  onChange: (addresses: Address[]) => void;
  googleApiKey?: string;
}

const AVAILABLE_ADDRESS_TAGS = [
  "Home",
  "Work",
  "Current",
  "Previous",
  "Family",
  "Vacation",
];

export function AddressInput({ addresses, onChange, googleApiKey }: AddressInputProps) {
  const [newAddress, setNewAddress] = useState("");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (newAddress.length > 3 && googleApiKey) {
      // Use Google Places API (New) REST API
      const controller = new AbortController();
      
      const fetchSuggestions = async () => {
        try {
          const response = await fetch(
            `https://places.googleapis.com/v1/places:autocomplete`,
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": googleApiKey,
                "X-Goog-FieldMask": "suggestions.placePrediction.placeId,suggestions.placePrediction.text",
              },
              body: JSON.stringify({
                input: newAddress,
                includedPrimaryTypes: ["street_address", "premise"],
              }),
              signal: controller.signal,
            }
          );

          if (!response.ok) {
            throw new Error(`Places API error: ${response.status}`);
          }

          const data = await response.json();
          
          if (data.suggestions && data.suggestions.length > 0) {
            const addressSuggestions = data.suggestions
              .filter((s: any) => s.placePrediction && s.placePrediction.text)
              .map((s: any) => {
                // Handle different possible structures
                const text = s.placePrediction.text;
                if (typeof text === "string") {
                  return text;
                } else if (text && typeof text === "object" && "text" in text) {
                  return text.text;
                } else {
                  // Fallback: try to extract any string value
                  console.warn("Unexpected text structure:", text);
                  return String(text);
                }
              })
              .filter((text: string) => text && typeof text === "string");
            setSuggestions(addressSuggestions);
            setShowSuggestions(true);
          } else {
            setSuggestions([]);
          }
        } catch (error: any) {
          if (error.name !== "AbortError") {
            console.error("Error fetching place suggestions:", error);
            setSuggestions([]);
          }
        }
      };

      // Debounce: wait 300ms after user stops typing
      const timeoutId = setTimeout(() => {
        fetchSuggestions();
      }, 300);

      return () => {
        clearTimeout(timeoutId);
        controller.abort();
      };
    } else {
      setSuggestions([]);
      setShowSuggestions(false);
    }
  }, [newAddress, googleApiKey]);

  const handleAdd = (addressText?: string) => {
    const addr = addressText || newAddress.trim();
    if (addr) {
      onChange([
        ...addresses.map((a) => ({ ...a, isCurrent: false })),
        {
          id: Date.now().toString(),
          address: addr,
          tags: [],
          isCurrent: addresses.length === 0, // First address is current by default
        },
      ]);
      setNewAddress("");
      setShowSuggestions(false);
    }
  };

  const handleUpdate = (id: string, updates: Partial<Address>) => {
    if (updates.isCurrent) {
      // Only one address can be current
      onChange(
        addresses.map((a) => (a.id === id ? { ...a, ...updates } : { ...a, isCurrent: false }))
      );
    } else {
      onChange(addresses.map((a) => (a.id === id ? { ...a, ...updates } : a)));
    }
  };

  const handleDelete = (id: string) => {
    onChange(addresses.filter((a) => a.id !== id));
  };

  return (
    <div className="space-y-3">
      {addresses.map((address) => (
        <div key={address.id} className="border rounded-lg p-3 space-y-2">
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <div className="font-medium text-sm flex-1">{address.address}</div>
                {address.isCurrent && (
                  <Badge variant="default" className="text-xs">
                    Current
                  </Badge>
                )}
              </div>
              <CategoryButtons
                categories={AVAILABLE_ADDRESS_TAGS}
                selected={address.tags}
                onChange={(selected) => handleUpdate(address.id, { tags: selected })}
              />
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleUpdate(address.id, { isCurrent: !address.isCurrent })}
                className="mt-2"
              >
                {address.isCurrent ? "Remove as Current" : "Set as Current"}
              </Button>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => handleDelete(address.id)}
              className="h-8 w-8 p-0"
            >
              <Trash2 className="h-4 w-4 text-destructive" />
            </Button>
          </div>
        </div>
      ))}

      <div className="border-2 border-dashed rounded-lg p-3 space-y-2">
        <div className="relative">
          <Input
            ref={inputRef}
            value={newAddress}
            onChange={(e) => {
              setNewAddress(e.target.value);
              setShowSuggestions(true);
            }}
            onFocus={() => setShowSuggestions(suggestions.length > 0)}
            placeholder="Start typing address..."
            className="flex-1"
          />
          {showSuggestions && suggestions.length > 0 && (
            <div className="absolute z-10 mt-1 w-full bg-popover border rounded-md shadow-md max-h-40 overflow-auto">
              {suggestions.map((suggestion, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleAdd(suggestion)}
                  className="w-full text-left px-3 py-2 hover:bg-accent text-sm flex items-center gap-2"
                >
                  <MapPin className="h-4 w-4 text-muted-foreground" />
                  {suggestion}
                </button>
              ))}
            </div>
          )}
        </div>
        {!googleApiKey && (
          <p className="text-xs text-muted-foreground">
            Google Places API not configured. Manual entry only.
          </p>
        )}
      </div>
    </div>
  );
}

