// Single query-key factory (doc 06 §2). Both direct hooks and SSE-driven cache
// patches use these, so key usage stays consistent across paths.
export const keys = {
  health: ["health"] as const,
  settings: (section: string) => ["settings", section] as const,
  books: ["books"] as const,
  book: (id: string) => ["book", id] as const,
  bookUi: (id: string) => ["bookUi", id] as const,
  parts: (bookId: string) => ["parts", bookId] as const,
  chapters: (bookId: string) => ["chapters", bookId] as const,
  plotlines: (bookId: string) => ["plotlines", bookId] as const,
  characters: (bookId: string) => ["characters", bookId] as const,
  characterRelationships: (bookId: string) => ["characterRelationships", bookId] as const,
  scenes: (bookId: string) => ["scenes", bookId] as const,
  scene: (bookId: string, sceneId: string) => ["scene", bookId, sceneId] as const,
  todos: (bookId: string, includeScenes: boolean) => ["todos", bookId, includeScenes] as const,
  sceneTodos: (bookId: string, sceneId: string) => ["sceneTodos", bookId, sceneId] as const,
  conversations: (bookId: string, sceneId: string) => ["conversations", bookId, sceneId] as const,
  conversation: (bookId: string, conversationId: string) => ["conversation", bookId, conversationId] as const,
  git: (bookId: string) => ["git", bookId] as const,
  compileCheck: (bookId: string) => ["compileCheck", bookId] as const,
};
