import { NextResponse } from "next/server";

export async function proxyToBackend(req: Request, endpoint: string): Promise<NextResponse> {
  const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";
  
  try {
    const body = await req.json();

    const r = await fetch(`${backendUrl}${endpoint}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store"
    });

    const text = await r.text();
    return new NextResponse(text, {
      status: r.status,
      headers: { "content-type": r.headers.get("content-type") ?? "application/json" }
    });
  } catch (error) {
    console.error(`[API Proxy Error] ${endpoint}:`, error);
    return new NextResponse(
      JSON.stringify({ error: "Internal server error" }),
      {
        status: 500,
        headers: { "content-type": "application/json" }
      }
    );
  }
}
