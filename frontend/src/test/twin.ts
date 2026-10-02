import type { Localized } from "../api/types";

/** A fixture's `{en, my}` twin; `my` defaults to the English, for tests that only read English. */
export function twin(en: string, my: string = en): Localized {
  return { en, my };
}
