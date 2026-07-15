import { useQuery } from "@tanstack/react-query";

import * as api from "../api/settings";
import { keys } from "./keys";

export const useUser = () => useQuery({ queryKey: keys.settings("user"), queryFn: api.getUser });
export const useModels = () => useQuery({ queryKey: keys.settings("models"), queryFn: api.listModels });
export const useAI = () => useQuery({ queryKey: keys.settings("ai"), queryFn: api.getAI });
export const useJobs = () => useQuery({ queryKey: keys.settings("ai-jobs"), queryFn: api.listJobs });
export const usePlaceholders = () =>
  useQuery({ queryKey: keys.settings("placeholders"), queryFn: api.listPlaceholders, staleTime: Infinity });
