"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { api } from "@/lib/api-client";
import { PROPERTY_TYPES, PROPERTY_CONDITIONS } from "@/lib/constants";
import type { PropertyCondition, ValuationResponse } from "@/lib/types";

const schema = z.object({
  address: z.string().min(3, "Enter at least 3 characters"),
  property_type: z.enum([
    "apartment",
    "house",
    "villa",
    "studio",
    "maisonette",
    "penthouse",
  ]),
  area_sqm: z.coerce.number().positive("Area must be positive").max(10000),
  floor: z.coerce.number().int().optional().or(z.literal("")),
  rooms: z.coerce.number().int().positive().optional().or(z.literal("")),
  bedrooms: z.coerce.number().int().min(0).optional().or(z.literal("")),
  bathrooms: z.coerce.number().int().min(0).optional().or(z.literal("")),
  year_built: z.coerce.number().int().min(1400).max(2030).optional().or(z.literal("")),
  condition: z
    .enum(["new", "excellent", "good", "needs_renovation", "shell"])
    .optional()
    .or(z.literal("")),
  has_parking: z.boolean().optional(),
  has_garden: z.boolean().optional(),
  has_pool: z.boolean().optional(),
  has_elevator: z.boolean().optional(),
  has_balcony: z.boolean().optional(),
});

type FormData = z.infer<typeof schema>;

interface PropertyFormProps {
  countryCode: string;
  countryKey: string;
  onResult: (result: ValuationResponse, coords?: [number, number]) => void;
}

export function PropertyForm({
  countryCode,
  onResult,
}: PropertyFormProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      property_type: "apartment",
    },
  });

  const onSubmit = async (data: FormData) => {
    setLoading(true);
    setError(null);

    try {
      // First geocode the address
      const geo = await api.geocode.lookup(data.address, countryCode);

      // Then get valuation
      const result = await api.valuations.estimate({
        country_code: countryCode,
        lat: geo.lat,
        lon: geo.lon,
        address: data.address,
        property_type: data.property_type,
        area_sqm: data.area_sqm,
        floor: data.floor !== "" ? Number(data.floor) : undefined,
        rooms: data.rooms !== "" ? Number(data.rooms) : undefined,
        bedrooms: data.bedrooms !== "" ? Number(data.bedrooms) : undefined,
        bathrooms: data.bathrooms !== "" ? Number(data.bathrooms) : undefined,
        year_built: data.year_built !== "" ? Number(data.year_built) : undefined,
        condition: data.condition ? data.condition as PropertyCondition : undefined,
        has_parking: data.has_parking,
        has_garden: data.has_garden,
        has_pool: data.has_pool,
        has_elevator: data.has_elevator,
        has_balcony: data.has_balcony,
      });

      onResult(result, [geo.lat, geo.lon]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to get valuation");
    } finally {
      setLoading(false);
    }
  };

  const inputClass =
    "w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm focus:border-[var(--color-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]";
  const labelClass = "mb-1 block text-sm font-medium text-[var(--color-text)]";

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      className="space-y-6 rounded-xl border border-[var(--color-border)] p-6"
    >
      <h3 className="text-lg font-semibold">Property Details</h3>

      {/* Address */}
      <div>
        <label className={labelClass}>Address *</label>
        <input
          {...register("address")}
          placeholder="e.g. 123 Republic Street, Valletta"
          className={inputClass}
        />
        {errors.address && (
          <p className="mt-1 text-xs text-red-500">{errors.address.message}</p>
        )}
      </div>

      {/* Type and Area */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className={labelClass}>Property Type *</label>
          <select {...register("property_type")} className={inputClass}>
            {PROPERTY_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className={labelClass}>Area (m²) *</label>
          <input
            type="number"
            {...register("area_sqm")}
            placeholder="e.g. 85"
            className={inputClass}
          />
          {errors.area_sqm && (
            <p className="mt-1 text-xs text-red-500">
              {errors.area_sqm.message}
            </p>
          )}
        </div>
      </div>

      {/* Floor and Rooms */}
      <div className="grid grid-cols-3 gap-4">
        <div>
          <label className={labelClass}>Floor</label>
          <input
            type="number"
            {...register("floor")}
            placeholder="e.g. 3"
            className={inputClass}
          />
        </div>
        <div>
          <label className={labelClass}>Rooms</label>
          <input
            type="number"
            {...register("rooms")}
            placeholder="e.g. 4"
            className={inputClass}
          />
        </div>
        <div>
          <label className={labelClass}>Bedrooms</label>
          <input
            type="number"
            {...register("bedrooms")}
            placeholder="e.g. 2"
            className={inputClass}
          />
        </div>
      </div>

      {/* Year and Condition */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className={labelClass}>Year Built</label>
          <input
            type="number"
            {...register("year_built")}
            placeholder="e.g. 2005"
            className={inputClass}
          />
        </div>
        <div>
          <label className={labelClass}>Condition</label>
          <select {...register("condition")} className={inputClass}>
            <option value="">Select...</option>
            {PROPERTY_CONDITIONS.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Amenities */}
      <div>
        <label className={labelClass}>Amenities</label>
        <div className="flex flex-wrap gap-4">
          {[
            { key: "has_parking", label: "Parking" },
            { key: "has_garden", label: "Garden" },
            { key: "has_pool", label: "Pool" },
            { key: "has_elevator", label: "Elevator" },
            { key: "has_balcony", label: "Balcony" },
          ].map(({ key, label }) => (
            <label key={key} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                {...register(key as keyof FormData)}
                className="rounded"
              />
              {label}
            </label>
          ))}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Submit */}
      <button
        type="submit"
        disabled={loading}
        className="w-full rounded-lg bg-[var(--color-primary)] py-3 text-sm font-medium text-white transition-colors hover:bg-[var(--color-primary-dark)] disabled:opacity-50"
      >
        {loading ? "Estimating..." : "Get Price Estimate"}
      </button>
    </form>
  );
}
