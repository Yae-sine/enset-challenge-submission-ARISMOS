"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
} from "recharts";

interface SessionResult {
  session_id: string;
  status: string;
  nom: string;
  serie_bac: string;
  domain_scores: Record<string, number>;
  learning_style: string;
  filieres_count: number;
  top_3: Array<{
    rang: number;
    filiere_id: string;
    filiere_nom: string;
    type: string;
    ville: string;
    score_final: number;
    justification: string;
    plan_action_30j: string[];
    prochaine_etape: string;
  }>;
  pdf_path?: string;
  error?: string;
}

interface AgentEvent {
  agent: string;
  message: string;
  data?: Record<string, unknown>;
}

function ResultsContent() {
  const searchParams = useSearchParams();
  const sessionId = searchParams.get("session_id");

  const [status, setStatus] = useState<"loading" | "complete" | "error">("loading");
  const [result, setResult] = useState<SessionResult | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) {
      setError("Session ID manquant");
      setStatus("error");
      return;
    }

    // Connect to SSE for live updates
    const eventSource = new EventSource(`/api/session/${sessionId}/status`);

    eventSource.addEventListener("agent_start", (e) => {
      const data = JSON.parse(e.data);
      setEvents((prev) => [...prev, data]);
    });

    eventSource.addEventListener("agent_done", (e) => {
      const data = JSON.parse(e.data);
      setEvents((prev) => [...prev, { ...data, message: `${data.agent} terminé ✓` }]);
    });

    eventSource.addEventListener("complete", async () => {
      eventSource.close();
      // Fetch final results
      try {
        const res = await fetch(`/api/session/${sessionId}/result`);
        const data = await res.json();
        setResult(data);
        setStatus("complete");
      } catch {
        setError("Erreur lors de la récupération des résultats");
        setStatus("error");
      }
    });

    eventSource.addEventListener("error", (e) => {
      console.error("SSE error:", e);
      eventSource.close();
      setError("Connexion perdue. Rechargez la page.");
      setStatus("error");
    });

    return () => {
      eventSource.close();
    };
  }, [sessionId]);

  if (status === "loading") {
    return <LoadingScreen events={events} />;
  }

  if (status === "error" || !result) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-red-600 mb-4">Erreur</h1>
          <p className="text-gray-600 mb-6">{error || "Une erreur est survenue"}</p>
          <Link
            href="/onboarding"
            className="px-6 py-3 bg-orient-blue text-white rounded-lg"
          >
            Recommencer
          </Link>
        </div>
      </div>
    );
  }

  return <ResultsDashboard result={result} />;
}

function LoadingScreen({ events }: { events: AgentEvent[] }) {
  const agentNames: Record<string, string> = {
    profileur: "📊 Analyse du profil",
    explorateur: "🔍 Recherche des filières",
    conseiller: "🎯 Préparation des recommandations",

    pdf_generator: "📄 Création du rapport",
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full mx-4">
        <div className="bg-white rounded-xl shadow-lg p-8 text-center">
          <div className="animate-spin w-16 h-16 border-4 border-orient-blue border-t-transparent rounded-full mx-auto mb-6" />
          <h2 className="text-xl font-bold text-gray-900 mb-2">
            Analyse en cours...
          </h2>
          <p className="text-gray-600 mb-6">
            Nos 4 agents IA travaillent sur ton profil
          </p>

          <div className="space-y-3 text-left">
            {events.map((event, i) => (
              <div
                key={i}
                className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg"
              >
                <span className="text-lg">
                  {event.message.includes("✓") ? "✅" : "⏳"}
                </span>
                <span className="text-sm text-gray-700">
                  {agentNames[event.agent] || event.agent}: {event.message}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function ResultsDashboard({ result }: { result: SessionResult }) {
  const [selectedFiliere, setSelectedFiliere] = useState<string | null>(null);

  // Prepare radar chart data
  const radarData = Object.entries(result.domain_scores).map(([domain, score]) => ({
    domain: domain.charAt(0).toUpperCase() + domain.slice(1),
    score: Math.round(score * 100),
    fullMark: 100,
  }));

  const handleSelectFiliere = async (filiereId: string) => {
    setSelectedFiliere(filiereId);
    // Redirect to interview page
    window.location.href = `/interview?session_id=${result.session_id}&filiere_id=${filiereId}`;
  };

  return (
    <main className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-6xl mx-auto px-4">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-orient-blue mb-2">
            🎓 Tes résultats, {result.nom} !
          </h1>
          <p className="text-gray-600">
            Voici ton analyse personnalisée basée sur {result.filieres_count} filières explorées
          </p>
        </div>

        <div className="grid lg:grid-cols-3 gap-6">
          {/* Radar Chart */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-xl shadow-lg p-6">
              <h2 className="text-lg font-bold text-gray-900 mb-4">
                📊 Ton profil par domaine
              </h2>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <RadarChart data={radarData}>
                    <PolarGrid />
                    <PolarAngleAxis dataKey="domain" tick={{ fontSize: 12 }} />
                    <PolarRadiusAxis angle={30} domain={[0, 100]} />
                    <Radar
                      name="Score"
                      dataKey="score"
                      stroke="#1E40AF"
                      fill="#1E40AF"
                      fillOpacity={0.5}
                    />
                  </RadarChart>
                </ResponsiveContainer>
              </div>

              <div className="mt-4 pt-4 border-t">
                <p className="text-sm text-gray-600">
                  <strong>Style d&apos;apprentissage:</strong>{" "}
                  <span className="text-orient-blue">{result.learning_style}</span>
                </p>
              </div>
            </div>

            {/* Actions */}
            <div className="bg-white rounded-xl shadow-lg p-6 mt-6">
              <h3 className="font-bold text-gray-900 mb-4">📥 Téléchargements</h3>
              <a
                href={`/api/session/${result.session_id}/pdf`}
                className="block w-full py-3 bg-orient-green text-white text-center rounded-lg font-medium hover:bg-green-700"
              >
                📄 Télécharger le rapport PDF
              </a>
            </div>
          </div>

          {/* Top 3 Recommendations */}
          <div className="lg:col-span-2">
            <h2 className="text-xl font-bold text-gray-900 mb-4">
              🎯 Top 3 Filières Recommandées
            </h2>

            <div className="space-y-4">
              {result.top_3.map((filiere, index) => (
                <div
                  key={filiere.filiere_id}
                  className="bg-white rounded-xl shadow-lg p-6 hover:shadow-xl transition-shadow"
                >
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <div className="flex items-center gap-3 mb-2">
                        <span className="text-2xl font-bold text-orient-blue">
                          #{index + 1}
                        </span>
                        <h3 className="text-lg font-bold text-gray-900">
                          {filiere.filiere_nom}
                        </h3>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <span className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded-full">
                          {filiere.type}
                        </span>
                        <span className="px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded-full">
                          📍 {filiere.ville}
                        </span>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-2xl font-bold text-orient-green">
                        {Math.round(filiere.score_final * 100)}%
                      </div>
                      <div className="text-xs text-gray-500">score match</div>
                    </div>
                  </div>

                  <p className="text-gray-700 mb-4">{filiere.justification}</p>

                  {filiere.plan_action_30j && filiere.plan_action_30j.length > 0 && (
                    <details className="mb-4">
                      <summary className="text-sm font-medium text-orient-blue cursor-pointer">
                        📋 Voir le plan d&apos;action (30 jours)
                      </summary>
                      <ul className="mt-2 space-y-1 text-sm text-gray-600 pl-4">
                        {filiere.plan_action_30j.map((step, i) => (
                          <li key={i} className="flex gap-2">
                            <span className="text-orient-blue">→</span>
                            {step}
                          </li>
                        ))}
                      </ul>
                    </details>
                  )}

                  <button
                    onClick={() => handleSelectFiliere(filiere.filiere_id)}
                    disabled={selectedFiliere === filiere.filiere_id}
                    className="w-full py-3 bg-orient-blue text-white rounded-lg font-medium hover:bg-blue-800 disabled:opacity-50"
                  >
                    🎤 Simuler un entretien pour cette filière
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}

export default function ResultsPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin w-8 h-8 border-4 border-orient-blue border-t-transparent rounded-full" />
      </div>
    }>
      <ResultsContent />
    </Suspense>
  );
}
