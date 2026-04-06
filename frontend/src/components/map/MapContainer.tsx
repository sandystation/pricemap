"use client";

import { MapContainer as LeafletMap, TileLayer, Marker, Popup } from "react-leaflet";
import L from "leaflet";
import { TILE_LAYER_URL, TILE_LAYER_ATTRIBUTION } from "@/lib/constants";
import type { ComparableProperty } from "@/lib/types";

// Fix Leaflet default icon issue with bundlers
const DefaultIcon = L.icon({
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
});

const ComparableIcon = L.icon({
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [20, 33],
  iconAnchor: [10, 33],
  popupAnchor: [1, -28],
  className: "opacity-70",
});

interface MapContainerProps {
  center: [number, number];
  zoom: number;
  countryCode: string;
  comparables?: ComparableProperty[];
  markerPosition?: [number, number] | null;
}

export default function MapContainer({
  center,
  zoom,
  comparables,
  markerPosition,
}: MapContainerProps) {
  return (
    <LeafletMap
      center={center}
      zoom={zoom}
      className="h-[500px] w-full"
      scrollWheelZoom={true}
    >
      <TileLayer url={TILE_LAYER_URL} attribution={TILE_LAYER_ATTRIBUTION} />

      {/* Main property marker */}
      {markerPosition && (
        <Marker position={markerPosition} icon={DefaultIcon}>
          <Popup>Your property</Popup>
        </Marker>
      )}

      {/* Comparable property markers */}
      {comparables?.map((comp) => (
        <Marker
          key={comp.id}
          position={[comp.lat, comp.lon]}
          icon={ComparableIcon}
        >
          <Popup>
            <div className="text-sm">
              <p className="font-semibold">
                {new Intl.NumberFormat("en", {
                  style: "currency",
                  currency: "EUR",
                  maximumFractionDigits: 0,
                }).format(comp.price_eur)}
              </p>
              <p>
                {comp.area_sqm} m² | {comp.property_type}
              </p>
              <p className="text-gray-500">
                {Math.round(comp.distance_m)}m away
              </p>
              {comp.address && (
                <p className="mt-1 text-xs text-gray-400">{comp.address}</p>
              )}
            </div>
          </Popup>
        </Marker>
      ))}
    </LeafletMap>
  );
}
