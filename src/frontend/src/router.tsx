import { createBrowserRouter, Navigate } from "react-router-dom";

import App from "./App";
import BookshelfPage from "./features/bookshelf/BookshelfPage";
import BookPage from "./features/book/BookPage";
import GraphPage from "./features/graph/GraphPage";
import ScenesTablePage from "./features/table/ScenesTablePage";
import EditorPage from "./features/editor/EditorPage";
import MetadataPage from "./features/metadata/MetadataPage";
import NotFound from "./features/NotFound";
import SettingsLayout from "./features/settings/SettingsLayout";
import UserSettingsPage from "./features/settings/UserSettingsPage";
import AISettingsPage from "./features/settings/AISettingsPage";
import AIJobsPage from "./features/settings/AIJobsPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <BookshelfPage /> },
      { path: "book/:bookId", element: <BookPage /> },
      { path: "book/:bookId/graph", element: <GraphPage /> },
      { path: "book/:bookId/table", element: <ScenesTablePage /> },
      { path: "book/:bookId/metadata", element: <MetadataPage /> },
      { path: "book/:bookId/scene/:sceneId", element: <EditorPage /> },
      {
        path: "settings",
        element: <SettingsLayout />,
        children: [
          { index: true, element: <Navigate to="user" replace /> },
          { path: "user", element: <UserSettingsPage /> },
          { path: "ai", element: <AISettingsPage /> },
          { path: "ai-jobs", element: <AIJobsPage /> },
        ],
      },
      { path: "*", element: <NotFound /> },
    ],
  },
]);
