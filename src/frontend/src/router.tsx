import { createBrowserRouter, Navigate } from "react-router-dom";

import App from "./App";
import BookshelfPage from "./features/bookshelf/BookshelfPage";
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
