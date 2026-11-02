import { engineGet } from "../proxy";

export async function GET(): Promise<Response> {
  return engineGet("/api/corridor");
}
