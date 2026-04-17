// src/app/layout.tsx
// Only import globals.css — Next.js + Tailwind JIT compiles everything from there.
// Do NOT import /public/styles.css; that file is a stale static build artifact.

import './globals.css'

export const metadata = {
  title:       'Prabhupada GPT',
  description: 'Teachings of A.C. Bhaktivedanta Swami Prabhupada',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}