"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { api } from "@/lib/api-client";
import { PROPERTY_TYPES, PROPERTY_CONDITIONS } from "@/lib/constants";
import type { PropertyCondition, ValuationResponse } from "@/lib/types";

const MAX_IMAGES = 10;
const MAX_IMAGE_BYTES = 8 * 1024 * 1024;
const MAX_TOTAL_IMAGE_BYTES = 40 * 1024 * 1024;
const MAX_DESCRIPTION_CHARS = 6000;

const schema = z.object({
  listing_type: z.enum(["sale", "rent"]),
  address: z.string().min(3, "Enter at least 3 characters"),
  // Beta covers Malta apartments only (the enriched model + backend accept
  // apartment only); the selector is likewise limited to apartment.
  property_type: z.enum(["apartment"]),
  area_sqm: z.coerce.number().positive("Area must be positive").max(10000),
  floor: z.coerce.number().int().min(-2).max(100).optional().or(z.literal("")),
  total_floors: z.coerce.number().int().min(1).max(100).optional().or(z.literal("")),
  total_int_area: z.coerce.number().positive().max(10000).optional().or(z.literal("")),
  total_ext_area: z.coerce.number().min(0).max(10000).optional().or(z.literal("")),
  rooms: z.coerce.number().int().min(1).max(50).optional().or(z.literal("")),
  bedrooms: z.coerce.number().int().min(0).max(20).optional().or(z.literal("")),
  bathrooms: z.coerce.number().int().min(0).max(20).optional().or(z.literal("")),
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
  description: z
    .string()
    .min(20, "Enter at least 20 characters")
    .max(MAX_DESCRIPTION_CHARS, `Use ${MAX_DESCRIPTION_CHARS} characters or fewer`),
}).refine((data) => (
  data.floor === "" ||
  data.total_floors === "" ||
  Number(data.floor) <= Number(data.total_floors)
), {
  message: "Floor cannot exceed total floors",
  path: ["floor"],
}).refine((data) => (
  data.total_int_area === "" ||
  Number(data.total_int_area) <= Number(data.area_sqm)
), {
  message: "Internal area cannot exceed total area",
  path: ["total_int_area"],
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
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [images, setImages] = useState<FileList | null>(null);

  const validateImages = (files: FileList | null) => {
    if (!files || files.length === 0) {
      setImages(null);
      return;
    }
    if (files.length > MAX_IMAGES) {
      setImages(null);
      setError(`Upload at most ${MAX_IMAGES} images`);
      return;
    }
    let totalBytes = 0;
    for (const file of Array.from(files)) {
      totalBytes += file.size;
      if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
        setImages(null);
        setError("Images must be JPG, PNG, or WebP");
        return;
      }
      if (file.size > MAX_IMAGE_BYTES) {
        setImages(null);
        setError("Each image must be under 8MB");
        return;
      }
    }
    if (totalBytes > MAX_TOTAL_IMAGE_BYTES) {
      setImages(null);
      setError("Total image upload must be under 40MB");
      return;
    }
    setError(null);
    setImages(files);
  };

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      listing_type: "sale",
      property_type: "apartment",
    },
  });
  const listingType = watch("listing_type");

  const onSubmit = async (data: FormData) => {
    setLoading(true);
    setError(null);
    setStatusMessage("Uploading case details");

    try {
      const formData = new globalThis.FormData();
      const append = (key: string, value: unknown) => {
        if (value !== undefined && value !== null && value !== "") {
          formData.append(key, String(value));
        }
      };

      append("country_code", countryCode);
      append("listing_type", data.listing_type);
      append("address", data.address);
      append("property_type", data.property_type);
      append("area_sqm", data.area_sqm);
      append("floor", data.floor);
      append("total_floors", data.total_floors);
      append("total_int_area", data.total_int_area);
      append("total_ext_area", data.total_ext_area);
      append("rooms", data.rooms);
      append("bedrooms", data.bedrooms);
      append("bathrooms", data.bathrooms);
      append("year_built", data.year_built);
      append("condition", data.condition as PropertyCondition | "");
      append("has_parking", Boolean(data.has_parking));
      append("has_garden", Boolean(data.has_garden));
      append("has_pool", Boolean(data.has_pool));
      append("has_elevator", Boolean(data.has_elevator));
      append("has_balcony", Boolean(data.has_balcony));
      append("description", data.description);
      if (images) {
        Array.from(images).forEach((file) => {
          formData.append("images", file);
        });
      }

      const job = await api.valuations.submitEnriched(formData);
      setStatusMessage("Queued for enrichment");

      for (let attempt = 0; attempt < 240; attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, 2000));
        const status = await api.valuations.getEnriched(job.job_id);
        setStatusMessage(status.message || `Status: ${status.status}`);

        if (status.status === "failed") {
          throw new Error(status.error || "Enriched valuation failed");
        }
        if (status.status === "complete" && status.result) {
          onResult(
            status.result,
            status.lat && status.lon ? [status.lat, status.lon] : undefined
          );
          setStatusMessage("Model-backed valuation complete");
          return;
        }
      }

      throw new Error("Valuation is still running. Try refreshing the result shortly.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to get valuation");
    } finally {
      setLoading(false);
      setStatusMessage(null);
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
      <div>
        <h3 className="text-lg font-semibold">Property Details</h3>
        <p className="mt-1 text-sm text-[var(--color-text-secondary)]">
          Add the same facts, description, and photos a listing would use for
          model-backed enrichment.
        </p>
      </div>

      <div>
        <label className={labelClass}>Valuation Type *</label>
        <div className="grid grid-cols-2 gap-2 rounded-lg bg-[var(--color-bg-secondary)] p-1">
          {[
            { value: "sale", label: "Sale" },
            { value: "rent", label: "Rent" },
          ].map((item) => (
            <label
              key={item.value}
              className={`flex cursor-pointer items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium ${
                listingType === item.value
                  ? "bg-[var(--color-bg)] text-[var(--color-primary)] shadow-sm"
                  : "text-[var(--color-text-secondary)]"
              }`}
            >
              <input
                type="radio"
                value={item.value}
                {...register("listing_type")}
                className="sr-only"
              />
              {item.label}
            </label>
          ))}
        </div>
      </div>

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
            {PROPERTY_TYPES.filter((t) => t.value === "apartment").map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
          <p className="mt-1 text-xs text-gray-400">Malta apartments (beta)</p>
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
          <label className={labelClass}>Total Floors</label>
          <input
            type="number"
            {...register("total_floors")}
            placeholder="e.g. 8"
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
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div>
          <label className={labelClass}>Bedrooms</label>
          <input
            type="number"
            {...register("bedrooms")}
            placeholder="e.g. 2"
            className={inputClass}
          />
        </div>
        <div>
          <label className={labelClass}>Bathrooms</label>
          <input
            type="number"
            {...register("bathrooms")}
            placeholder="e.g. 2"
            className={inputClass}
          />
        </div>
        <div>
          <label className={labelClass}>Internal m²</label>
          <input
            type="number"
            {...register("total_int_area")}
            placeholder="e.g. 92"
            className={inputClass}
          />
        </div>
      </div>

      {/* Year and Condition */}
      <div className="grid grid-cols-3 gap-4">
        <div>
          <label className={labelClass}>External m²</label>
          <input
            type="number"
            {...register("total_ext_area")}
            placeholder="e.g. 12"
            className={inputClass}
          />
        </div>
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

      <div>
        <label className={labelClass}>Description *</label>
        <textarea
          {...register("description")}
          rows={5}
          placeholder="Paste the listing-style description, including finish, views, outdoor space, parking, and location notes."
          className={inputClass}
        />
        {errors.description && (
          <p className="mt-1 text-xs text-red-500">{errors.description.message}</p>
        )}
      </div>

      <div>
        <label className={labelClass}>Photos</label>
        <input
          type="file"
          accept="image/png,image/jpeg,image/webp"
          multiple
          onChange={(event) => validateImages(event.target.files)}
          className={inputClass}
        />
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

      {statusMessage && (
        <div className="rounded-lg bg-blue-50 p-3 text-sm text-blue-700">
          {statusMessage}
        </div>
      )}

      {/* Submit */}
      <button
        type="submit"
        disabled={loading}
        className="w-full rounded-lg bg-[var(--color-primary)] py-3 text-sm font-medium text-white transition-colors hover:bg-[var(--color-primary-dark)] disabled:opacity-50"
      >
        {loading ? "Running Enrichment..." : "Run Model-Backed Valuation"}
      </button>
    </form>
  );
}
