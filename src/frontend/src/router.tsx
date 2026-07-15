import { createBrowserRouter } from "react-router-dom";

import App from "./App";
import BookshelfPage from "./features/bookshelf/BookshelfPage";
import NotFound from "./features/NotFound";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <BookshelfPage /> },
      { path: "*", element: <NotFound /> },
    ],
  },
]);
