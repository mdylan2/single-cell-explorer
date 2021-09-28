import { selectIsUserStateDirty as genesets } from "./genesets";

export const selectIsUserStateDirty = (state: any) => {
  const selectors = [genesets];

  return selectors.some((selector) => selector(state));
};
