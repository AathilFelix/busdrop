/* Server-side proxy to the BusDrop engine (FastAPI).
   The browser stays same-origin; only this server code talks to :8000.
   Override with BUSDROP_ENGINE=http://host:8000. */

const ENGINE = process.env.BUSDROP_ENGINE ?? "http://127.0.0.1:8000";

function engineDown(): Response {
  return Response.json(
    { detail: "BusDrop engine unreachable at " + ENGINE },
    { status: 503 },
  );
}

export async function engineGet(path: string): Promise<Response> {
  let res: Response;
  try {
    res = await fetch(`${ENGINE}${path}`, { cache: "no-store" });
  } catch {
    return engineDown();
  }
  return Response.json(await res.json(), { status: res.status });
}

export async function enginePost(path: string, req: Request): Promise<Response> {
  let body: string;
  try {
    body = await req.text();
  } catch {
    return Response.json({ detail: "unreadable body" }, { status: 400 });
  }
  let res: Response;
  try {
    res = await fetch(`${ENGINE}${path}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body,
    });
  } catch {
    return engineDown();
  }
  return Response.json(await res.json(), { status: res.status });
}
