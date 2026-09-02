import React, { useEffect, useState } from "react";
import StickyFilterBar from "../components/StickyFilterBar.jsx";
import MapView from "../components/MapView.jsx";
import MapControlsPanel from "../components/MapControlsPanel.jsx";
import OperatorComparisonTable from "../components/OperatorComparisonTable.jsx";
import RsrpTrendChart from "../components/RsrpTrendChart.jsx";
import LogDiagnostics from "../components/diagnostics/LogDiagnostics.jsx";
import { getLocationOverview, getDelegationOverview } from "../api/client";

export default function UserDashboard() {
  const [selection, setSelection] = useState({
    gouvernoratId: null,
    delegationId: null,
    secteurId: null,
  });
  const [operatorFilter, setOperatorFilter] = useState("ALL");
  const [overview, setOverview] = useState(null);
  const [scope, setScope] = useState(null); // 'secteur' | 'delegation' | null
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [layerKey, setLayerKey] = useState("auto");
  const [showBadPoints, setShowBadPoints] = useState(true);
  const [badPointsCount, setBadPointsCount] = useState(0);
  // NEW: filters the map's bad-points layer by source type ('all' |
  // 'rsrp' | 'http_attempt'). Lives here alongside layerKey/showBadPoints
  // since it's the same controlled-prop pattern shared by MapView and
  // MapControlsPanel.
  const [pointsFilter, setPointsFilter] = useState("all");

  const { secteurId, delegationId, gouvernoratId } = selection;
  const level = secteurId
    ? "secteur"
    : delegationId
      ? "delegation"
      : gouvernoratId
        ? "gouvernorat"
        : null;
  const id = secteurId || delegationId || gouvernoratId || null;

  useEffect(() => {
    setError(null);

    if (secteurId) {
      setScope("secteur");
      setLoading(true);
      getLocationOverview(secteurId)
        .then(setOverview)
        .catch((err) => {
          console.error("location-overview fetch failed:", err);
          setOverview(null);
          setError(
            err.response
              ? `Erreur ${err.response.status}: ${err.response.data?.detail || "echec de la requete"}`
              : "Impossible de contacter le serveur.",
          );
        })
        .finally(() => setLoading(false));
    } else if (delegationId) {
      setScope("delegation");
      setLoading(true);
      getDelegationOverview(delegationId)
        .then(setOverview)
        .catch((err) => {
          console.error("delegation-overview fetch failed:", err);
          setOverview(null);
          setError(
            err.response
              ? `Erreur ${err.response.status}: ${err.response.data?.detail || "echec de la requete"}`
              : "Impossible de contacter le serveur.",
          );
        })
        .finally(() => setLoading(false));
    } else {
      setScope(null);
      setOverview(null);
    }
  }, [secteurId, delegationId]);

  // Client-side filter of the comparison table rows by the selected
  // operator - the map's area-quality coloring is filtered server-side
  // (see MapView's `operator` prop), this keeps the table in sync.
  const filteredComparison = (overview?.comparison || []).filter(
    (row) => operatorFilter === "ALL" || row.operator === operatorFilter,
  );

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 24,
        maxWidth: 1280,
      }}
    >
      <div>
        <h1 style={{ fontSize: 22, marginBottom: 4 }}>Tableau de bord QoS</h1>
        <p style={{ color: "var(--text-muted)", margin: 0 }}>
          Selectionnez un gouvernorat/delegation pour une note globale, ou un
          secteur pour le detail.
        </p>
      </div>

      <StickyFilterBar
        onSelectionChange={setSelection}
        operatorFilter={operatorFilter}
        onOperatorChange={setOperatorFilter}
      />

      {error && (
        <div
          style={{
            color: "var(--signal-poor)",
            fontSize: 13,
            padding: "10px 14px",
            background: "var(--signal-poor-dim)",
            borderRadius: 6,
          }}
        >
          {error}
        </div>
      )}

      <div style={{ display: "flex", gap: 16, alignItems: "stretch" }}>
        <div style={{ flex: "0 0 260px" }}>
          <MapControlsPanel
            layerKey={layerKey}
            onLayerChange={setLayerKey}
            showBadPoints={showBadPoints}
            onToggleBadPoints={() => setShowBadPoints((v) => !v)}
            badPointsCount={badPointsCount}
            pointsFilter={pointsFilter}
            onPointsFilterChange={setPointsFilter}
          />
        </div>
        <div style={{ flex: 1 }}>
          <MapView
            secteurId={secteurId}
            delegationId={delegationId}
            gouvernoratId={gouvernoratId}
            operator={operatorFilter}
            height={320}
            layerKey={layerKey}
            showBadPoints={showBadPoints}
            onBadPointsChange={setBadPointsCount}
            pointsFilter={pointsFilter}
          />
        </div>
      </div>

      <div>
        <div className="eyebrow" style={{ marginBottom: 10 }}>
          Comparaison par operateur{" "}
          {scope === "delegation" ? "(moyenne de la delegation)" : ""}
        </div>
        <OperatorComparisonTable rows={filteredComparison} scope={scope} />
      </div>

      <RsrpTrendChart level={level} id={id} operator={operatorFilter} />

      <LogDiagnostics level={level} id={id} operator={operatorFilter} />
    </div>
  );
}