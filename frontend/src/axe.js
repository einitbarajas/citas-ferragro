import React from "react";
import ReactDOM from "react-dom";

/** Solo en desarrollo; carga dinámica para no incluir axe-core en el bundle de producción. */
export async function initAxe() {
  if (!import.meta.env.DEV) return;
  const { default: axe } = await import("@axe-core/react");
  await axe(React, ReactDOM, 1000, {}, { include: [["#root"]] });
}
