import React from "react";
import ReactDOM from "react-dom";
import axe from "@axe-core/react";

export async function initAxe() {
  if (!import.meta.env.DEV) return;
  await axe(React, ReactDOM, 1000, {}, { include: [["#root"]] });
}
