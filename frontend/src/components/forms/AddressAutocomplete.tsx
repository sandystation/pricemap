"use client";

import { useEffect, useRef, useState } from "react";

import { api } from "@/lib/api-client";
import type { GeocodeCandidate } from "@/lib/types";
import { inputClass } from "@/lib/ui";

interface Props {
  value: string;
  onChangeText: (text: string) => void; // manual typing
  onSelect: (c: GeocodeCandidate) => void; // a suggestion was picked
  onClearCoords: () => void; // manual edit invalidates a prior pick
  countryCode?: string;
  placeholder?: string;
  id?: string;
}

// Debounced Malta address typeahead. Suggestions come from the auth-gated
// /api/v1/geocode/search endpoint; on any failure it returns [] so the user can
// still submit a free-typed address (geocoded server-side).
export function AddressAutocomplete({
  value,
  onChangeText,
  onSelect,
  onClearCoords,
  countryCode = "MT",
  placeholder,
  id = "address",
}: Props) {
  const [items, setItems] = useState<GeocodeCandidate[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [active, setActive] = useState(-1);
  const abortRef = useRef<AbortController | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const justSelected = useRef(false);
  const blurTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    // A selection sets the input text — don't re-search for it.
    if (justSelected.current) {
      justSelected.current = false;
      return;
    }
    clearTimeout(debounceRef.current);
    const q = value.trim();
    if (q.length < 3) {
      setItems([]);
      setOpen(false);
      setLoading(false);
      return;
    }
    setLoading(true);
    setOpen(true);
    debounceRef.current = setTimeout(async () => {
      abortRef.current?.abort();
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      const results = await api.geocode.search(q, countryCode, 6, ctrl.signal);
      if (ctrl.signal.aborted) return; // a newer keystroke superseded this
      setItems(results);
      setActive(-1);
      setLoading(false);
    }, 300);
    return () => clearTimeout(debounceRef.current);
  }, [value, countryCode]);

  useEffect(() => () => clearTimeout(blurTimer.current), []);

  function choose(c: GeocodeCandidate) {
    justSelected.current = true;
    onChangeText(c.display_name);
    onSelect(c);
    setItems([]);
    setOpen(false);
    setActive(-1);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!open || items.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(i + 1, items.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && active >= 0) {
      e.preventDefault();
      choose(items[active]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  const listId = `${id}-listbox`;
  const showList = open && value.trim().length >= 3;

  return (
    <div className="relative">
      <input
        id={id}
        type="text"
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={active >= 0 ? `${id}-opt-${active}` : undefined}
        autoComplete="off"
        value={value}
        placeholder={placeholder}
        className={inputClass}
        onChange={(e) => {
          onChangeText(e.target.value);
          onClearCoords();
        }}
        onKeyDown={onKeyDown}
        onFocus={() => items.length > 0 && setOpen(true)}
        onBlur={() => {
          blurTimer.current = setTimeout(() => setOpen(false), 150);
        }}
      />
      {showList && (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-20 mt-1 max-h-64 w-full overflow-auto rounded-lg border border-[var(--color-border)] bg-white shadow-lg"
        >
          {loading && (
            <li className="px-3 py-2 text-sm text-[var(--color-text-secondary)]" aria-live="polite">
              Searching…
            </li>
          )}
          {!loading && items.length === 0 && (
            <li className="px-3 py-2 text-sm text-[var(--color-text-secondary)]" aria-live="polite">
              No matches in Malta
            </li>
          )}
          {!loading &&
            items.map((c, i) => (
              <li
                key={`${c.lat},${c.lon},${i}`}
                id={`${id}-opt-${i}`}
                role="option"
                aria-selected={i === active}
                onMouseDown={(e) => {
                  e.preventDefault(); // keep focus; fire before onBlur closes the list
                  choose(c);
                }}
                onMouseEnter={() => setActive(i)}
                className={`cursor-pointer px-3 py-2 text-sm ${
                  i === active ? "bg-[var(--color-bg-secondary)]" : ""
                }`}
              >
                {c.display_name}
              </li>
            ))}
        </ul>
      )}
    </div>
  );
}
