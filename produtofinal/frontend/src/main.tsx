import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fortawesome/fontawesome-free/css/all.min.css";
import "@/design-system/prototipo-v1.css";
import "@/design-system/overrides.css";

import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "@/app/App";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
