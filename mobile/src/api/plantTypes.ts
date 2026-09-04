import { apiRequest } from "./client";
import type { PlantTypeOut } from "../types/api";

export function listPlantTypes(): Promise<PlantTypeOut[]> {
  return apiRequest<PlantTypeOut[]>("/api/plant-types");
}
