import { createContext, useContext } from "react";

import type { Meta } from "../api/types";

export const MetaContext = createContext<Meta | null>(null);

/** GET /meta, loaded once by MetaProvider. */
export function useMeta(): Meta {
  const meta = useContext(MetaContext);
  if (!meta) throw new Error("useMeta must be used inside MetaProvider");
  return meta;
}
