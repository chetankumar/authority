import { useQuery } from "@tanstack/react-query";

import * as api from "../api/books";
import { keys } from "./keys";

export const useBooks = () => useQuery({ queryKey: keys.books, queryFn: api.listBooks });
export const useBook = (id: string) =>
  useQuery({ queryKey: keys.book(id), queryFn: () => api.getBook(id), enabled: !!id });
