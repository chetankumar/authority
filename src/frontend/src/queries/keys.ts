// Single query-key factory (doc 06 §2). Both direct hooks and SSE-driven cache
// patches use these, so key usage stays consistent across paths.
export const keys = {
  health: ["health"] as const,
  settings: (section: string) => ["settings", section] as const,
  books: ["books"] as const,
  book: (id: string) => ["book", id] as const,
  bookUi: (id: string) => ["bookUi", id] as const,
  scenes: (bookId: string) => ["scenes", bookId] as const,
  scene: (bookId: string, sceneId: string) => ["scene", bookId, sceneId] as const,
  todos: (bookId: string) => ["todos", bookId] as const,
  git: (bookId: string) => ["git", bookId] as const,
  compileCheck: (bookId: string) => ["compileCheck", bookId] as const,
};
