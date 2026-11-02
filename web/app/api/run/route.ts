import { enginePost } from "../proxy";

export async function POST(req: Request): Promise<Response> {
  // Spark runs reason over every meet and take minutes; no timeout here.
  return enginePost("/api/run", req);
}
