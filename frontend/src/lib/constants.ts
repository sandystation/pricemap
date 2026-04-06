export const PROPERTY_TYPES = [
  { value: "apartment", label: "Apartment" },
  { value: "house", label: "House" },
  { value: "villa", label: "Villa" },
  { value: "studio", label: "Studio" },
  { value: "maisonette", label: "Maisonette" },
  { value: "penthouse", label: "Penthouse" },
] as const;

export const PROPERTY_CONDITIONS = [
  { value: "new", label: "New / Under Construction" },
  { value: "excellent", label: "Excellent" },
  { value: "good", label: "Good" },
  { value: "needs_renovation", label: "Needs Renovation" },
  { value: "shell", label: "Shell / Unfinished" },
] as const;

export const TILE_LAYER_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
export const TILE_LAYER_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
