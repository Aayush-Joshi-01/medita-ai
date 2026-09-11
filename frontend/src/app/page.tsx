export default function HomePage() {
  return (
    <main className="flex min-h-screen items-center justify-center p-8">
      <div className="max-w-lg text-center">
        <h1 className="text-2xl font-semibold">medita-ai</h1>
        <p className="mt-2 text-sm text-neutral-500">
          Scaffolding stage — this page only confirms the frontend container
          builds, serves, and is reachable through the reverse proxy. The
          real application UI (auth, dashboard, AI doctor, imaging,
          transcription, knowledge base) lands in build step 6.
        </p>
      </div>
    </main>
  );
}
