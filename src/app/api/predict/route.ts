import { NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/api-proxy";

export const runtime = "nodejs";

export async function POST(req: Request): Promise<NextResponse> {
  return proxyToBackend(req, "/api/predict");
}

