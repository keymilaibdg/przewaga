import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

// Register the service worker only on real origins (not in sandboxed previews).
// Sandboxed frames throw on navigator.serviceWorker access, hence the try/catch.
window.addEventListener("load", () => {
  try {
    if (!__NATIVE__ && "serviceWorker" in navigator && window.isSecureContext) {
      navigator.serviceWorker.register("/sw.js").catch((err) => console.warn("SW registration failed", err));
    }
  } catch (err) {
    console.warn("Service worker unavailable in this context", err);
  }
});
