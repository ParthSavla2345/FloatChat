"use client";

import { useEffect } from "react";
import { CircleMarker, MapContainer, Popup, TileLayer, useMap } from "react-leaflet";
import { formatDateTime } from "@/lib/format";
import type { MapProfileRecord } from "@/lib/types";

function FitProfiles({ profiles }: { profiles: MapProfileRecord[] }) {
  const map = useMap();
  useEffect(() => {
    if (profiles.length > 1) {
      map.fitBounds(
        profiles.map((profile) => [profile.latitude, profile.longitude] as [number, number]),
        { padding: [24, 24], maxZoom: 7 },
      );
    } else if (profiles.length === 1) {
      map.setView([profiles[0].latitude, profiles[0].longitude], 6);
    }
  }, [map, profiles]);
  return null;
}

export function ArgoMap({
  profiles,
  onSelect,
}: {
  profiles: MapProfileRecord[];
  onSelect: (profile: MapProfileRecord) => void;
}) {
  return (
    <div className="map-frame">
      <MapContainer center={[-8, 82]} zoom={3} scrollWheelZoom className="h-full w-full">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitProfiles profiles={profiles} />
        {profiles.map((profile, index) => (
          <CircleMarker
            key={profile.profile_key}
            center={[profile.latitude, profile.longitude]}
            radius={6}
            pathOptions={{
              color: "#075985",
              weight: 1,
              fillColor: index % 2 ? "#38bdf8" : "#0e7490",
              fillOpacity: 0.8,
            }}
            eventHandlers={{ click: () => onSelect(profile) }}
          >
            <Popup>
              <strong>Profile {profile.profile_number}</strong>
              <br />
              Project float key: {profile.float_id}
              <br />
              {profile.latitude.toFixed(3)}, {profile.longitude.toFixed(3)}
              <br />
              {formatDateTime(profile.datetime)}
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  );
}
