import { spawn } from "node:child_process";
import { access } from "node:fs/promises";
import path from "node:path";
import { NextRequest, NextResponse } from "next/server";

type RouteContext = { params: Promise<{ action: string }> };

const backendScript = (repoRoot: string) => `
import json, os, sys
repo_root = json.loads(${JSON.stringify(JSON.stringify(repoRoot))})
backend_dir = os.path.join(repo_root, "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
from services.profile_explorer_service import get_profile_explorer_service
service = get_profile_explorer_service()
action = sys.argv[1]
args = json.loads(sys.argv[2])
try:
    if action == "summary":
        result = service.get_summary()
    elif action == "profiles":
        result = service.list_profiles(**args)
    elif action == "map":
        result = service.map_profiles(**args)
    elif action == "profile":
        result = service.get_profile(
            args["file_name"],
            args["profile_number"],
            limit=args.get("limit", 5000),
        )
    else:
        raise ValueError("Unsupported data action.")
except ValueError as exc:
    print(json.dumps({"error": str(exc), "kind": "validation"}))
    sys.exit(2)
print(json.dumps(result, default=str))
`;

async function findPython(repoRoot: string) {
  const candidates = [
    process.env.OCEANIQ_PYTHON_PATH || "",
    process.env.PYTHON_PATH || "",
    path.join(repoRoot, ".venv", "Scripts", "python.exe"),
    path.join(repoRoot, ".venv", "bin", "python"),
  ].filter(Boolean);
  for (const candidate of candidates) {
    try {
      await access(candidate);
      return candidate;
    } catch {
      continue;
    }
  }
  return "python";
}

async function invokeBackend(action: string, args: Record<string, unknown>) {
  const repoRoot = path.resolve(process.cwd(), "..");
  const python = await findPython(repoRoot);
  const child = spawn(
    /*turbopackIgnore: true*/ python,
    [ "-c", backendScript(repoRoot), action, JSON.stringify(args) ],
    { cwd: repoRoot, env: process.env },
  );

  const output = await new Promise<{ stdout: string; stderr: string; code: number | null }>((resolve, reject) => {
    let stdout = "";
    let stderr = "";
    const timer = setTimeout(() => {
      child.kill();
      reject(new Error("Backend data request timed out."));
    }, 90000);
    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      resolve({ stdout, stderr, code });
    });
  });

  let payload: Record<string, unknown>;
  try {
    payload = JSON.parse(output.stdout.trim()) as Record<string, unknown>;
  } catch {
    throw new Error("Backend returned an unreadable data response.");
  }
  if (output.code === 2) {
    return { payload, status: 400 };
  }
  if (output.code !== 0) {
    throw new Error("Backend data request failed.");
  }
  return { payload, status: 200 };
}

export async function GET(request: NextRequest, context: RouteContext) {
  const { action } = await context.params;
  const search = request.nextUrl.searchParams;
  let args: Record<string, unknown> = {};

  try {
    const numericKeys = ["limit", "offset", "latitude_min", "latitude_max", "longitude_min", "longitude_max", "profile_number"];
    for (const key of numericKeys) {
      if (!search.has(key)) continue;
      const value = Number(search.get(key));
      if (!Number.isFinite(value) || (["limit", "offset", "profile_number"].includes(key) && !Number.isInteger(value))) {
        return NextResponse.json({ error: `${key} must be a valid ${["limit", "offset", "profile_number"].includes(key) ? "integer" : "coordinate"}.` }, { status: 400 });
      }
    }

    if (action === "profiles" || action === "map") {
      if ((search.get("search") || "").length > 256) {
        return NextResponse.json({ error: "search must be 256 characters or fewer." }, { status: 400 });
      }
      args = {
        search: search.get("search") || undefined,
        parameter: search.get("parameter") || undefined,
        region: search.get("region") || undefined,
        start_datetime: search.get("start_datetime") || undefined,
        end_datetime: search.get("end_datetime") || undefined,
        limit: search.has("limit") ? Number(search.get("limit")) : undefined,
        latitude_min: search.has("latitude_min") ? Number(search.get("latitude_min")) : undefined,
        latitude_max: search.has("latitude_max") ? Number(search.get("latitude_max")) : undefined,
        longitude_min: search.has("longitude_min") ? Number(search.get("longitude_min")) : undefined,
        longitude_max: search.has("longitude_max") ? Number(search.get("longitude_max")) : undefined,
      };
      if (action === "profiles") {
        args.offset = search.has("offset") ? Number(search.get("offset")) : 0;
      }
    } else if (action === "profile") {
      const fileName = search.get("file_name");
      const profileNumber = Number(search.get("profile_number"));
      if (!fileName || !Number.isInteger(profileNumber)) {
        return NextResponse.json({ error: "file_name and integer profile_number are required." }, { status: 400 });
      }
      args = {
        file_name: fileName,
        profile_number: profileNumber,
        limit: search.has("limit") ? Number(search.get("limit")) : undefined,
      };
    } else if (action !== "summary") {
      return NextResponse.json({ error: "Unknown data endpoint." }, { status: 404 });
    }

    const result = await invokeBackend(action, args);
    return NextResponse.json(result.payload, { status: result.status });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Backend data request failed.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
