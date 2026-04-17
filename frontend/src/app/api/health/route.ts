import { NextResponse } from "next/server"

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000"

export async function GET() {
  try {
    const res = await fetch(`${BACKEND_URL}/health`, { cache: "no-store" })
    const text = await res.text()
    return new NextResponse(text, {
      status: res.status,
      headers: { "Content-Type": res.headers.get("content-type") || "application/json" },
    })
  } catch (error) {
    const message = error instanceof Error ? error.message : "Health proxy failed"
    return NextResponse.json({ detail: message }, { status: 500 })
  }
}
