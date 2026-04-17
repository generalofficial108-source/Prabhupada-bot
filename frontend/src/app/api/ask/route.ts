import { NextResponse } from "next/server"

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000"

export async function POST(req: Request) {
  try {
    const body = await req.json()
    const res = await fetch(`${BACKEND_URL}/api/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    })

    const text = await res.text()
    return new NextResponse(text, {
      status: res.status,
      headers: { "Content-Type": res.headers.get("content-type") || "application/json" },
    })
  } catch (error) {
    const message = error instanceof Error ? error.message : "Proxy request failed"
    return NextResponse.json({ detail: message }, { status: 500 })
  }
}
