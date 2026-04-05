"use client";

import Link from "next/link";

export default function Home() {
  return (
    <main className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold text-orient-blue">🎓 OrientAgent</h1>
          <span className="text-sm text-gray-500">Hackathon ENSET 2026</span>
        </div>
      </header>

      {/* Hero Section */}
      <section className="flex-1 flex items-center justify-center px-4 py-16">
        <div className="max-w-3xl text-center">
          <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-6">
            Trouve ta voie avec
            <span className="text-orient-blue"> l&apos;IA</span>
          </h2>

          <p className="text-xl text-gray-600 mb-8">
            OrientAgent analyse ton profil, explore 40+ filières marocaines
            vérifiées, et te recommande les meilleures options pour ton avenir.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center mb-12">
            <Link
              href="/onboarding"
              className="px-8 py-4 bg-orient-blue text-white rounded-lg font-semibold text-lg hover:bg-blue-800 transition-colors shadow-lg"
            >
              🚀 Commencer mon orientation
            </Link>
          </div>

          {/* Features */}
          <div className="grid md:grid-cols-4 gap-6 mt-12">
            <FeatureCard
              icon="📊"
              title="Analyse de profil"
              description="Scoring précis par domaine basé sur tes notes et intérêts"
            />
            <FeatureCard
              icon="🔍"
              title="Recherche RAG"
              description="Base de données de 40+ filières marocaines vérifiées"
            />
            <FeatureCard
              icon="🎯"
              title="Top 3 personnalisé"
              description="Recommandations avec plan d'action sur 30 jours"
            />

          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-gray-800 text-white py-6">
        <div className="max-w-7xl mx-auto px-4 text-center">
          <p className="text-gray-400">
            OrientAgent — Hackathon ENSET 2026 — IA Agentique & Education
          </p>
        </div>
      </footer>
    </main>
  );
}

function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: string;
  title: string;
  description: string;
}) {
  return (
    <div className="bg-white p-6 rounded-xl shadow-md hover:shadow-lg transition-shadow">
      <div className="text-4xl mb-3">{icon}</div>
      <h3 className="font-semibold text-gray-900 mb-2">{title}</h3>
      <p className="text-sm text-gray-600">{description}</p>
    </div>
  );
}
