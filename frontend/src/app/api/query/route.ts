import { spawn } from "node:child_process";
import path from "node:path";
import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as { question?: string };
    const question = typeof body.question === "string" ? body.question.trim() : "";

    if (!question) {
      return NextResponse.json({ error: "A natural-language question is required." }, { status: 400 });
    }

    const repoRoot = path.resolve(process.cwd(), "..");
    const pythonCandidates = [
      process.env.OCEANIQ_PYTHON_PATH || "",
      process.env.PYTHON_PATH || "",
      path.join(repoRoot, ".venv", "Scripts", "python.exe"),
      path.join(repoRoot, ".venv", "bin", "python"),
      "python",
    ].filter(Boolean);

    const script = `
import json, os, sys
repo_root = r"${repoRoot.replace(/\\/g, "\\\\")}" 
backend_dir = os.path.join(repo_root, "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from services.orchestration_service import OrchestrationService

question = json.loads(sys.argv[1])
result = OrchestrationService().execute(question)
print(json.dumps(result.model_dump(mode="json"), default=str))
`;

    let pythonBinary: string | undefined;
    for (const candidate of pythonCandidates) {
      if (candidate === "python") {
        pythonBinary = candidate;
        break;
      }
      if (await fileExists(candidate)) {
        pythonBinary = candidate;
        break;
      }
    }

    if (!pythonBinary) {
      throw new Error("Python environment for backend services was not found.");
    }

    const child = spawn(/*turbopackIgnore: true*/ pythonBinary, ["-c", script, JSON.stringify(question)], {
      cwd: repoRoot,
      env: process.env,
    });

    const { stdout: pythonStdout } = await new Promise<{ stdout: string; stderr: string }>((resolve, reject) => {
      let stdoutText = "";
      let stderrText = "";
      child.stdout.on("data", (chunk) => {
        stdoutText += chunk.toString();
      });
      child.stderr.on("data", (chunk) => {
        stderrText += chunk.toString();
      });
      child.on("error", reject);
      child.on("close", (code) => {
        if (code !== 0) {
          reject(new Error(stderrText || `Python subprocess exited with code ${code}.`));
          return;
        }
        resolve({ stdout: stdoutText, stderr: stderrText });
      });
    });

    const payload = JSON.parse(pythonStdout.trim());
    return NextResponse.json(payload);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unexpected backend error.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

async function fileExists(candidate: string) {
  const { access } = await import("node:fs/promises");
  try {
    await access(candidate);
    return true;
  } catch {
    return false;
  }
}
